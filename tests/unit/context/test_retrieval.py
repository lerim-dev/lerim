"""Unit tests for confidence + recency reranking and the relevance floor.

Covers the new pure-function ranking helpers in lerim.context.retrieval:
RRF_K's conventional value, the confidence and recency multipliers,
blend_confidence_and_recency, apply_relevance_floor, and SearchHit.confidence.

rrf_fuse's own rank-fusion formula (unaffected here beyond RRF_K's new value)
is already covered by tests/unit/context/test_store_search.py. Broad
end-to-end ranking validation is the lead's job, but
TestSearchRecordsThroughLiveStore pins the one behavior specific to this
lane's search_records restructuring: candidate metadata must be fetched and
reranked for the FULL fused set before the `limit` slice, not after.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

import lerim.context.retrieval as retrieval
from lerim.context.project_identity import resolve_project_identity
from lerim.context.retrieval import (
    CONFIDENCE_MULTIPLIER_CEILING,
    CONFIDENCE_MULTIPLIER_FLOOR,
    DEFAULT_LEXICAL_RRF_WEIGHT,
    DEFAULT_SEMANTIC_RRF_WEIGHT,
    RECENCY_BOOST_WEIGHT,
    RELEVANCE_FLOOR,
    RELEVANCE_FLOOR_REFERENCE_RANK,
    RRF_K,
    SearchHit,
    apply_relevance_floor,
    blend_confidence_and_recency,
    rrf_fuse,
)
from lerim.context.spec import DEFAULT_RECORD_CONFIDENCE
from lerim.context.store import ContextStore


def _base_hit_kwargs() -> dict:
    """Return a fresh kwargs dict for constructing a minimal SearchHit."""
    return dict(
        record_id="rec_1",
        project_id="proj_1",
        kind="fact",
        title="t",
        body="b",
        status="active",
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
        valid_from="2026-01-01T00:00:00+00:00",
        valid_until=None,
        score=0.5,
        sources=[],
    )


class TestRRFConstants:
    """RRF_K must use a conventional damping value, not the old over-eager one."""

    def test_rrf_k_is_conventional_60(self):
        assert RRF_K == 60

    def test_rrf_k_is_not_the_old_over_weighting_value(self):
        assert RRF_K != 2

    def test_default_weights_are_unchanged(self):
        assert DEFAULT_SEMANTIC_RRF_WEIGHT == 0.7
        assert DEFAULT_LEXICAL_RRF_WEIGHT == 0.3


class TestConfidenceMultiplier:
    """Tests for the private _confidence_multiplier helper."""

    def test_default_confidence_is_neutral(self):
        assert retrieval._confidence_multiplier(0.5) == pytest.approx(1.0)

    def test_zero_confidence_hits_the_floor(self):
        assert retrieval._confidence_multiplier(0.0) == pytest.approx(CONFIDENCE_MULTIPLIER_FLOOR)

    def test_full_confidence_hits_the_ceiling(self):
        assert retrieval._confidence_multiplier(1.0) == pytest.approx(CONFIDENCE_MULTIPLIER_CEILING)

    def test_monotonically_increasing_with_confidence(self):
        low = retrieval._confidence_multiplier(0.2)
        mid = retrieval._confidence_multiplier(0.5)
        high = retrieval._confidence_multiplier(0.8)
        assert low < mid < high

    def test_out_of_range_high_clamps_to_ceiling(self):
        assert retrieval._confidence_multiplier(5.0) == pytest.approx(CONFIDENCE_MULTIPLIER_CEILING)

    def test_out_of_range_low_clamps_to_floor(self):
        assert retrieval._confidence_multiplier(-5.0) == pytest.approx(CONFIDENCE_MULTIPLIER_FLOOR)


class TestRecencyMultipliers:
    """Tests for the private _recency_multipliers helper."""

    def test_single_candidate_is_neutral(self):
        result = retrieval._recency_multipliers({"r1": "2026-01-01T00:00:00+00:00"})
        assert result == {"r1": pytest.approx(1.0)}

    def test_empty_input_returns_empty(self):
        assert retrieval._recency_multipliers({}) == {}

    def test_newest_gets_full_positive_boost_oldest_full_penalty(self):
        result = retrieval._recency_multipliers(
            {
                "old": "2020-01-01T00:00:00+00:00",
                "new": "2026-01-01T00:00:00+00:00",
            }
        )
        assert result["new"] == pytest.approx(1.0 + RECENCY_BOOST_WEIGHT)
        assert result["old"] == pytest.approx(1.0 - RECENCY_BOOST_WEIGHT)

    def test_middle_candidate_lands_at_neutral(self):
        result = retrieval._recency_multipliers(
            {
                "old": "2026-01-01T00:00:00+00:00",
                "mid": "2026-01-02T00:00:00+00:00",
                "new": "2026-01-03T00:00:00+00:00",
            }
        )
        assert result["old"] < result["mid"] < result["new"]
        assert result["mid"] == pytest.approx(1.0)

    def test_identical_timestamps_are_all_neutral(self):
        result = retrieval._recency_multipliers(
            {
                "a": "2026-01-01T00:00:00+00:00",
                "b": "2026-01-01T00:00:00+00:00",
            }
        )
        assert result == {"a": pytest.approx(1.0), "b": pytest.approx(1.0)}

    def test_unparseable_timestamp_is_neutral_but_does_not_block_others(self):
        result = retrieval._recency_multipliers(
            {
                "old": "2020-01-01T00:00:00+00:00",
                "new": "2026-01-01T00:00:00+00:00",
                "bad": "not-a-timestamp",
            }
        )
        assert result["bad"] == pytest.approx(1.0)
        assert result["new"] > result["old"]

    def test_none_timestamp_is_neutral(self):
        assert retrieval._recency_multipliers({"r1": None}) == {"r1": pytest.approx(1.0)}

    def test_boost_never_exceeds_configured_weight(self):
        result = retrieval._recency_multipliers(
            {
                "old": "2000-01-01T00:00:00+00:00",
                "new": "2026-01-01T00:00:00+00:00",
            }
        )
        # Only two candidates, so the span is fully spent between them: the
        # newest/oldest land exactly on the configured +/- bound, never past it.
        assert result["new"] == pytest.approx(1.0 + RECENCY_BOOST_WEIGHT)
        assert result["old"] == pytest.approx(1.0 - RECENCY_BOOST_WEIGHT)


class TestParseUtcTimestamp:
    """Tests for the private _parse_utc_timestamp helper."""

    def test_parses_z_suffix_as_utc(self):
        result = retrieval._parse_utc_timestamp("2026-01-01T00:00:00Z")
        assert result is not None
        assert result.utcoffset().total_seconds() == 0

    def test_naive_datetime_is_assumed_utc(self):
        result = retrieval._parse_utc_timestamp("2026-01-01T00:00:00")
        assert result is not None
        assert result.utcoffset().total_seconds() == 0

    def test_none_returns_none(self):
        assert retrieval._parse_utc_timestamp(None) is None

    def test_empty_string_returns_none(self):
        assert retrieval._parse_utc_timestamp("") is None

    def test_garbage_string_returns_none(self):
        assert retrieval._parse_utc_timestamp("not-a-timestamp") is None


class TestBlendConfidenceAndRecency:
    """Prove confidence and recency reorder fused RRF candidates predictably."""

    def test_equal_confidence_and_recency_preserves_rrf_order(self):
        combined = [("r1", 0.02, ["semantic"]), ("r2", 0.01, ["fts"])]
        result = blend_confidence_and_recency(
            combined,
            confidence_by_id={"r1": 0.5, "r2": 0.5},
            updated_at_by_id={
                "r1": "2026-01-01T00:00:00+00:00",
                "r2": "2026-01-01T00:00:00+00:00",
            },
        )
        assert [record_id for record_id, _score, _sources in result] == ["r1", "r2"]

    def test_higher_confidence_can_overturn_a_lower_rrf_rank(self):
        # r2 trails r1 on raw RRF score, but r1 has been repeatedly marked wrong
        # (confidence 0.0) while r2 is fully confirmed (confidence 1.0).
        combined = [("r1", 0.02, ["semantic"]), ("r2", 0.015, ["semantic"])]
        result = blend_confidence_and_recency(
            combined,
            confidence_by_id={"r1": 0.0, "r2": 1.0},
            updated_at_by_id={
                "r1": "2026-01-01T00:00:00+00:00",
                "r2": "2026-01-01T00:00:00+00:00",
            },
        )
        assert result[0][0] == "r2"

    def test_recency_can_overturn_a_close_rrf_rank(self):
        combined = [("older", 0.0105, ["semantic"]), ("newer", 0.01, ["semantic"])]
        result = blend_confidence_and_recency(
            combined,
            confidence_by_id={"older": 0.5, "newer": 0.5},
            updated_at_by_id={
                "older": "2020-01-01T00:00:00+00:00",
                "newer": "2026-01-01T00:00:00+00:00",
            },
        )
        assert result[0][0] == "newer"

    def test_missing_metadata_defaults_to_neutral(self):
        combined = [("r1", 0.02, ["semantic"])]
        result = blend_confidence_and_recency(combined, confidence_by_id={}, updated_at_by_id={})
        assert result[0][1] == pytest.approx(0.02)

    def test_sources_are_preserved(self):
        combined = [("r1", 0.02, ["semantic", "fts"])]
        result = blend_confidence_and_recency(
            combined,
            confidence_by_id={"r1": 0.5},
            updated_at_by_id={"r1": "2026-01-01T00:00:00+00:00"},
        )
        assert result[0][2] == ["semantic", "fts"]

    def test_result_stays_sorted_descending(self):
        combined = [
            ("a", 0.005, ["fts"]),
            ("b", 0.02, ["semantic"]),
            ("c", 0.01, ["semantic", "fts"]),
        ]
        result = blend_confidence_and_recency(
            combined,
            confidence_by_id={"a": 0.9, "b": 0.1, "c": 0.5},
            updated_at_by_id={
                "a": "2026-01-01T00:00:00+00:00",
                "b": "2026-01-01T00:00:00+00:00",
                "c": "2026-01-01T00:00:00+00:00",
            },
        )
        scores = [score for _record_id, score, _sources in result]
        assert scores == sorted(scores, reverse=True)

    def test_empty_combined_returns_empty(self):
        assert blend_confidence_and_recency([], confidence_by_id={}, updated_at_by_id={}) == []


class TestApplyRelevanceFloor:
    """Prove the relevance floor drops weak candidates instead of forcing top-k."""

    def test_all_irrelevant_candidates_are_excluded(self):
        reranked = [
            ("r1", RELEVANCE_FLOOR / 100, ["semantic"]),
            ("r2", RELEVANCE_FLOOR / 50, ["fts"]),
            ("r3", 0.0, ["semantic"]),
        ]
        assert apply_relevance_floor(reranked) == []

    def test_relevant_candidates_survive(self):
        reranked = [("r1", RELEVANCE_FLOOR * 10, ["semantic"])]
        assert apply_relevance_floor(reranked) == reranked

    def test_mixed_set_keeps_only_qualifying_candidates(self):
        reranked = [
            ("strong", RELEVANCE_FLOOR * 5, ["semantic", "fts"]),
            ("weak", RELEVANCE_FLOOR / 10, ["semantic"]),
        ]
        result = apply_relevance_floor(reranked)
        assert [record_id for record_id, _score, _sources in result] == ["strong"]

    def test_boundary_score_is_inclusive(self):
        reranked = [("r1", RELEVANCE_FLOOR, ["semantic"])]
        assert apply_relevance_floor(reranked) == reranked

    def test_empty_input_returns_empty(self):
        assert apply_relevance_floor([]) == []

    def test_preserves_order_of_survivors(self):
        reranked = [
            ("first", RELEVANCE_FLOOR * 9, ["semantic"]),
            ("second", RELEVANCE_FLOOR * 3, ["fts"]),
        ]
        assert apply_relevance_floor(reranked) == reranked


class TestBlendAndFloorTogether:
    """The composed pipeline search_records actually runs: blend, then floor."""

    def test_all_deep_tail_candidates_are_excluded(self):
        # Every candidate is a weak, low-confidence, stale, single-source match --
        # exactly the "nothing here is a real match" scenario the floor exists for.
        combined = [(f"tail{i}", RELEVANCE_FLOOR * 0.3, ["semantic"]) for i in range(5)]
        confidence_by_id = {f"tail{i}": 0.1 for i in range(5)}
        updated_at_by_id = {f"tail{i}": "2015-01-01T00:00:00+00:00" for i in range(5)}

        reranked = blend_confidence_and_recency(
            combined,
            confidence_by_id=confidence_by_id,
            updated_at_by_id=updated_at_by_id,
        )

        assert apply_relevance_floor(reranked) == []

    def test_one_strong_candidate_survives_alongside_weak_ones(self):
        combined = [
            ("strong", RELEVANCE_FLOOR * 20, ["semantic", "fts"]),
            ("weak", RELEVANCE_FLOOR * 0.2, ["semantic"]),
        ]
        reranked = blend_confidence_and_recency(
            combined,
            confidence_by_id={"strong": 0.5, "weak": 0.5},
            updated_at_by_id={
                "strong": "2026-01-01T00:00:00+00:00",
                "weak": "2026-01-01T00:00:00+00:00",
            },
        )

        result = apply_relevance_floor(reranked)

        assert [record_id for record_id, _score, _sources in result] == ["strong"]


class TestConfidenceAndRecencyThroughRealFusedRanking:
    """Confidence/recency change the order of a real rrf_fuse() output.

    RRF_K=60 keeps the score gap between adjacent top ranks small (~1.6%, see
    RRF_K's docstring), which is precisely what lets a mild confidence or
    recency adjustment flip a close call -- these tests exercise that directly
    against rrf_fuse's real output rather than hand-built scores.
    """

    def test_confidence_reorders_a_real_fused_ranking(self):
        # r1 wins on raw RRF (present in both retrievers' rank 1); r2 only
        # appears once, at rank 2. Confidence should still flip the winner.
        combined = rrf_fuse(
            semantic_rows=[("r1", 0.0), ("r2", 0.1)],
            lexical_rows=[("r1", -5.0)],
            semantic_weight=DEFAULT_SEMANTIC_RRF_WEIGHT,
            lexical_weight=DEFAULT_LEXICAL_RRF_WEIGHT,
        )
        assert combined[0][0] == "r1"  # sanity check: raw RRF prefers r1

        reranked = blend_confidence_and_recency(
            combined,
            confidence_by_id={"r1": 0.0, "r2": 1.0},
            updated_at_by_id={
                "r1": "2026-01-01T00:00:00+00:00",
                "r2": "2026-01-01T00:00:00+00:00",
            },
        )

        assert reranked[0][0] == "r2"

    def test_recency_reorders_a_real_fused_ranking(self):
        # rank1_id barely beats rank2_id on raw RRF (adjacent single-source
        # ranks), but rank2_id is far more recently touched.
        combined = rrf_fuse(
            semantic_rows=[("rank1_id", 0.0), ("rank2_id", 0.1)],
            lexical_rows=[],
            semantic_weight=DEFAULT_SEMANTIC_RRF_WEIGHT,
            lexical_weight=DEFAULT_LEXICAL_RRF_WEIGHT,
        )
        assert combined[0][0] == "rank1_id"  # sanity check: raw RRF prefers rank1_id

        reranked = blend_confidence_and_recency(
            combined,
            confidence_by_id={"rank1_id": 0.5, "rank2_id": 0.5},
            updated_at_by_id={
                "rank1_id": "2020-01-01T00:00:00+00:00",
                "rank2_id": "2026-01-01T00:00:00+00:00",
            },
        )

        assert reranked[0][0] == "rank2_id"


class TestRelevanceFloorAtRealisticShortlistDepth:
    """The floor must have real teeth at the shipped default shortlist depth.

    Regression coverage for a calibration bug: RELEVANCE_FLOOR was originally
    5% of an idealized rank-1-in-both-retrievers ceiling, which turned out to
    be *larger* than the score a maximally weak candidate can still reach
    within a realistic shortlist -- RRF's rank-based score decays gently by
    design (see RRF_K), so a candidate ranked dead last within a full
    RELEVANCE_FLOOR_REFERENCE_RANK-deep shortlist (the shipped default
    `semantic_shortlist_size` / `lexical_shortlist_size`, see
    config/default.toml) still keeps a surprisingly large share of the
    ceiling. These tests build scores through the real rrf_fuse ->
    blend_confidence_and_recency -> apply_relevance_floor pipeline at that
    shortlist depth, rather than hand-picked multiples of RELEVANCE_FLOOR, so
    a future miscalibration fails a test derived from realistic scores
    instead of one derived from the same constant it is checking.
    """

    def _fused_at_reference_depth(
        self, weak_record_id: str
    ) -> list[tuple[str, float, list[str]]]:
        """Real rrf_fuse() output: `weak_record_id` ranked dead last in the
        semantic retriever alone, within a full RELEVANCE_FLOOR_REFERENCE_RANK
        deep shortlist (the only other retriever this candidate is absent
        from -- fts -- contributes nothing for it)."""
        filler_count = RELEVANCE_FLOOR_REFERENCE_RANK - 1
        semantic_rows = [(f"filler{i}", float(i)) for i in range(filler_count)] + [
            (weak_record_id, float(filler_count))
        ]
        return rrf_fuse(
            semantic_rows=semantic_rows,
            lexical_rows=[],
            semantic_weight=DEFAULT_SEMANTIC_RRF_WEIGHT,
            lexical_weight=DEFAULT_LEXICAL_RRF_WEIGHT,
        )

    def test_dead_last_discredited_stale_candidate_is_excluded(self):
        combined = self._fused_at_reference_depth("weakest")
        assert combined[-1][0] == "weakest"  # sanity: it really is ranked last

        confidence_by_id = {record_id: 0.5 for record_id, _score, _sources in combined}
        confidence_by_id["weakest"] = 0.0  # repeatedly marked wrong
        updated_at_by_id = {
            record_id: "2026-01-01T00:00:00+00:00" for record_id, _score, _sources in combined
        }
        updated_at_by_id["weakest"] = "2015-01-01T00:00:00+00:00"  # oldest -> max staleness

        reranked = blend_confidence_and_recency(
            combined, confidence_by_id=confidence_by_id, updated_at_by_id=updated_at_by_id
        )
        result = apply_relevance_floor(reranked)

        assert "weakest" not in [record_id for record_id, _score, _sources in result]

    def test_dead_last_but_merely_unconfirmed_candidate_still_survives(self):
        # Guards against over-tuning in the other direction: a candidate at
        # the same rock-bottom rank that is only unconfirmed (default
        # confidence) and not stale must still clear the floor. The floor is
        # meant to catch weak rank combined with active distrust/staleness,
        # not weak rank alone.
        combined = self._fused_at_reference_depth("plain")

        confidence_by_id = {record_id: DEFAULT_RECORD_CONFIDENCE for record_id, _score, _sources in combined}
        updated_at_by_id = {
            record_id: "2026-01-01T00:00:00+00:00" for record_id, _score, _sources in combined
        }

        reranked = blend_confidence_and_recency(
            combined, confidence_by_id=confidence_by_id, updated_at_by_id=updated_at_by_id
        )
        result = apply_relevance_floor(reranked)

        assert "plain" in [record_id for record_id, _score, _sources in result]


class TestSearchHitConfidenceField:
    """SearchHit gained a `confidence` field so callers can see earned confidence."""

    def test_confidence_defaults_to_the_spec_default(self):
        hit = SearchHit(**_base_hit_kwargs())
        assert hit.confidence == pytest.approx(DEFAULT_RECORD_CONFIDENCE)

    def test_confidence_can_be_set_explicitly(self):
        hit = SearchHit(confidence=0.9, **_base_hit_kwargs())
        assert hit.confidence == pytest.approx(0.9)

    def test_confidence_is_frozen(self):
        hit = SearchHit(**_base_hit_kwargs())
        with pytest.raises(FrozenInstanceError):
            hit.confidence = 0.1

    def test_constructing_without_confidence_kwarg_still_works(self):
        # Existing call sites (e.g. tests/unit/context/test_store_search.py)
        # construct SearchHit without a `confidence` kwarg; that must keep working.
        hit = SearchHit(**_base_hit_kwargs())
        assert hit.record_id == "rec_1"


class _RankOrderProvider:
    """Deterministic fake embeddings for TestSearchRecordsThroughLiveStore.

    `dominant` embeds identically to the query (semantic distance 0);
    `secondary` embeds further away but still on the same side of the space --
    a real, if weaker, semantic match. This gives raw RRF one unambiguous
    winner before any confidence adjustment.
    """

    model_id = "test-embed-rank-order"
    embedding_dims = 4

    def embed_query(self, text: str) -> list[float]:
        """Return a fixed query vector so document similarity is controllable."""
        del text
        return [1.0, 0.0, 0.0, 0.0]

    def embed_document(self, text: str) -> list[float]:
        """Return the dominant, secondary, or a neutral fallback vector."""
        lowered = text.lower()
        if "dominant marker" in lowered:
            return [1.0, 0.0, 0.0, 0.0]
        if "secondary marker" in lowered:
            return [0.6, 0.8, 0.0, 0.0]
        return [0.0, 0.0, 0.0, 1.0]


class TestSearchRecordsThroughLiveStore:
    """One end-to-end proof that Task 1's restructuring actually holds.

    search_records must fetch confidence/recency metadata and rerank the FULL
    fused candidate set BEFORE slicing to `limit`, not after. The pure-function
    tests elsewhere in this file already prove blend_confidence_and_recency and
    apply_relevance_floor work correctly in isolation; this test proves the
    wiring in search_records actually carries a trailing, confidence-boosted
    candidate through to a live ContextStore.search() result at a tight limit.
    If search_records ever regressed to slicing before fetching confidence,
    this is the test that would catch it: the confidence-boosted record would
    already be gone before it could win. Broader end-to-end ranking validation
    across more scenarios is the lead's job.
    """

    def _build_store(self, tmp_path, monkeypatch):
        """Build a ContextStore with one registered project and a fake embedder."""
        monkeypatch.setattr(
            "lerim.context.store.get_embedding_provider",
            lambda: _RankOrderProvider(),
        )
        db_path = tmp_path / "context.sqlite3"
        store = ContextStore(db_path)
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        identity = resolve_project_identity(repo_root)
        store.initialize()
        store.register_project(identity)
        store.upsert_session(
            project_id=identity.project_id,
            session_id="sess_search",
            agent_type="test",
            source_trace_ref="seed:search",
            repo_path=str(repo_root),
            cwd=str(repo_root),
            started_at="2026-04-18T00:00:00+00:00",
            model_name="test-model",
            instructions_text=None,
            prompt_text=None,
            metadata={},
        )
        return store, identity.project_id

    def test_confidence_boosted_trailing_record_wins_at_a_tight_limit(
        self, tmp_path, monkeypatch
    ):
        store, pid = self._build_store(tmp_path, monkeypatch)

        dominant = store.create_record(
            project_id=pid,
            session_id="sess_search",
            kind="fact",
            title="Dominant marker record",
            body=(
                "Dominant marker record repeats redis cache expiration "
                "redis cache expiration for a strong raw match."
            ),
        )
        secondary = store.create_record(
            project_id=pid,
            session_id="sess_search",
            kind="fact",
            title="Secondary marker record",
            body="Secondary marker record mentions redis cache expiration only once, in passing.",
        )

        # Pin both records to the same updated_at so recency cannot be the
        # thing that reorders them below -- confidence must do the work.
        with store.connect() as conn:
            conn.execute(
                "UPDATE records SET updated_at = ? WHERE record_id IN (?, ?)",
                (
                    "2026-01-01T00:00:00+00:00",
                    dominant["record_id"],
                    secondary["record_id"],
                ),
            )

        baseline = store.search(project_ids=[pid], query="redis cache expiration", limit=1)
        assert baseline[0].record_id == dominant["record_id"]  # sanity: raw RRF favors dominant

        # Discredit the raw winner and fully confirm the trailing record.
        with store.connect() as conn:
            conn.execute(
                "UPDATE records SET confidence = ? WHERE record_id = ?",
                (0.0, dominant["record_id"]),
            )
            conn.execute(
                "UPDATE records SET confidence = ? WHERE record_id = ?",
                (1.0, secondary["record_id"]),
            )

        hits = store.search(project_ids=[pid], query="redis cache expiration", limit=1)

        assert hits[0].record_id == secondary["record_id"]
