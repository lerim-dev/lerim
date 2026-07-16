"""Unit tests for the records.confidence migration and per-record feedback."""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import MagicMock

import pytest

from lerim.context.spec import (
    ALLOWED_FEEDBACK_SIGNALS,
    FEEDBACK_CONFIDENCE_DELTAS,
    next_record_confidence,
    normalize_feedback_signal,
)
from lerim.context.store import ContextStore


@pytest.fixture
def mock_embeddings(monkeypatch):
    """Deterministic embedding provider stub so tests avoid real model calls."""
    provider = MagicMock()
    provider.embedding_dims = 384
    provider.model_id = "test-model"
    provider.embed_document.return_value = [0.1] * 384
    provider.embed_query.return_value = [0.1] * 384
    monkeypatch.setattr("lerim.context.store.get_embedding_provider", lambda: provider)
    return provider


@pytest.fixture
def mock_store(tmp_path, mock_embeddings):
    """Fresh ContextStore with an initialized schema."""
    db_path = tmp_path / "context.sqlite3"
    s = ContextStore(db_path)
    s.initialize()
    return s


@pytest.fixture
def project_id(tmp_path, monkeypatch):
    """Deterministic project identity for tests."""
    monkeypatch.setattr(
        "lerim.config.project_scope.git_root_for",
        lambda _p=None: tmp_path,
    )
    from lerim.context.project_identity import resolve_project_identity

    return resolve_project_identity(tmp_path)


@pytest.fixture
def mock_seeded(mock_store, project_id):
    """Store with a registered project and one seeded session."""
    mock_store.register_project(project_id)
    mock_store.upsert_session(
        project_id=project_id.project_id,
        session_id="sess_test",
        agent_type="test",
        source_trace_ref="test.jsonl",
        repo_path=str(project_id.repo_path),
        cwd=str(project_id.repo_path),
        started_at="2026-01-01T00:00:00Z",
        model_name="test-model",
        instructions_text=None,
        prompt_text=None,
    )
    return mock_store, project_id.project_id


def _make_fact(store, project_id, **overrides):
    """Create a minimal fact record for feedback tests."""
    defaults = dict(
        project_id=project_id,
        session_id="sess_test",
        kind="fact",
        title="Confidence test fact",
        body="Feedback should earn or spend confidence deterministically.",
    )
    defaults.update(overrides)
    return store.create_record(**defaults)


# ---------------------------------------------------------------------------
# spec.py: FeedbackSignal / normalize_feedback_signal / next_record_confidence
# ---------------------------------------------------------------------------


class TestFeedbackSignalSpec:
    """Pure-function tests for the feedback signal contract in spec.py."""

    def test_allowed_feedback_signals(self):
        assert set(ALLOWED_FEEDBACK_SIGNALS) == {"used", "correct", "wrong", "confirm"}

    def test_normalize_accepts_allowed_values(self):
        for signal in ALLOWED_FEEDBACK_SIGNALS:
            assert normalize_feedback_signal(signal) == signal

    def test_normalize_is_case_and_whitespace_insensitive(self):
        assert normalize_feedback_signal(" CORRECT ") == "correct"

    def test_normalize_rejects_unknown_signal(self):
        with pytest.raises(ValueError, match="invalid_feedback_signal:bogus"):
            normalize_feedback_signal("bogus")

    def test_normalize_rejects_empty_signal(self):
        with pytest.raises(ValueError, match="invalid_feedback_signal:"):
            normalize_feedback_signal("")

    @pytest.mark.parametrize(
        ("signal", "expected_delta"),
        [("correct", 0.15), ("confirm", 0.15), ("used", 0.05), ("wrong", -0.25)],
    )
    def test_confidence_deltas(self, signal, expected_delta):
        assert FEEDBACK_CONFIDENCE_DELTAS[signal] == expected_delta

    def test_next_record_confidence_applies_delta(self):
        assert next_record_confidence(0.5, "correct") == pytest.approx(0.65)
        assert next_record_confidence(0.5, "confirm") == pytest.approx(0.65)
        assert next_record_confidence(0.5, "used") == pytest.approx(0.55)
        assert next_record_confidence(0.5, "wrong") == pytest.approx(0.25)

    def test_next_record_confidence_clamps_upper_bound(self):
        assert next_record_confidence(0.95, "correct") == pytest.approx(1.0)

    def test_next_record_confidence_clamps_lower_bound(self):
        assert next_record_confidence(0.1, "wrong") == pytest.approx(0.0)

    def test_next_record_confidence_rejects_invalid_signal(self):
        with pytest.raises(ValueError, match="invalid_feedback_signal:nope"):
            next_record_confidence(0.5, "nope")


# ---------------------------------------------------------------------------
# store.py: _ensure_record_confidence_schema migration
# ---------------------------------------------------------------------------


class TestEnsureRecordConfidenceSchema:
    """Tests for the records.confidence column migration."""

    def test_fresh_store_has_confidence_column_with_default(self, mock_store):
        with mock_store.connect() as conn:
            columns = mock_store._table_columns(conn, "records")
        assert "confidence" in columns

    def test_migration_adds_column_and_defaults_existing_rows(self, mock_seeded):
        store, pid = mock_seeded
        rec = _make_fact(store, pid)
        # Simulate a database created before the confidence column existed by
        # dropping it from an otherwise fully-migrated, populated database.
        with store.connect() as conn:
            conn.execute("ALTER TABLE records DROP COLUMN confidence")
            columns_before = store._table_columns(conn, "records")
        assert "confidence" not in columns_before

        # Re-run initialize(): this is the real upgrade path a pre-existing
        # on-disk database goes through, unmodified from production code.
        store.initialize()

        with store.connect() as conn:
            columns_after = store._table_columns(conn, "records")
            row = conn.execute(
                "SELECT confidence FROM records WHERE record_id = ?",
                (rec["record_id"],),
            ).fetchone()
        assert "confidence" in columns_after
        assert row["confidence"] == pytest.approx(0.5)

    def test_migration_idempotent(self, mock_store):
        mock_store.initialize()
        mock_store.initialize()
        with mock_store.connect() as conn:
            columns = mock_store._table_columns(conn, "records")
        assert "confidence" in columns

    def test_validate_schema_passes_with_confidence_column(self, mock_store):
        with mock_store.connect() as conn:
            mock_store._validate_schema(conn)  # must not raise

    def test_record_feedback_table_exists_after_initialize(self, mock_store):
        with mock_store.connect() as conn:
            assert mock_store._table_exists(conn, "record_feedback")

    def test_version_row_defaults_confidence_since_it_is_not_versioned(
        self, mock_seeded
    ):
        store, pid = mock_seeded
        rec = _make_fact(store, pid)
        store.record_feedback(rec["record_id"], "correct")
        fetched = store.fetch_record(rec["record_id"], include_versions=True)
        # record_versions has no confidence column, so version snapshots always
        # report the default -- confidence is not versioned history.
        assert fetched["versions"][0]["confidence"] == pytest.approx(0.5)
        assert fetched["confidence"] == pytest.approx(0.65)


# ---------------------------------------------------------------------------
# store.py: ContextStore.record_feedback
# ---------------------------------------------------------------------------


class TestRecordFeedback:
    """Tests for ContextStore.record_feedback."""

    def test_new_record_starts_at_default_confidence(self, mock_seeded):
        store, pid = mock_seeded
        rec = _make_fact(store, pid)
        assert rec["confidence"] == pytest.approx(0.5)

    def test_correct_signal_increases_confidence(self, mock_seeded):
        store, pid = mock_seeded
        rec = _make_fact(store, pid)
        result = store.record_feedback(rec["record_id"], "correct")
        assert result == {
            "record_id": rec["record_id"],
            "confidence": pytest.approx(0.65),
            "signal": "correct",
        }

    def test_confirm_signal_increases_confidence(self, mock_seeded):
        store, pid = mock_seeded
        rec = _make_fact(store, pid)
        result = store.record_feedback(rec["record_id"], "confirm")
        assert result["confidence"] == pytest.approx(0.65)

    def test_used_signal_increases_confidence_slightly(self, mock_seeded):
        store, pid = mock_seeded
        rec = _make_fact(store, pid)
        result = store.record_feedback(rec["record_id"], "used")
        assert result["confidence"] == pytest.approx(0.55)

    def test_wrong_signal_decreases_confidence(self, mock_seeded):
        store, pid = mock_seeded
        rec = _make_fact(store, pid)
        result = store.record_feedback(rec["record_id"], "wrong")
        assert result["confidence"] == pytest.approx(0.25)

    def test_confidence_clamps_at_upper_bound(self, mock_seeded):
        store, pid = mock_seeded
        rec = _make_fact(store, pid)
        for _ in range(6):
            result = store.record_feedback(rec["record_id"], "correct")
        assert result["confidence"] == pytest.approx(1.0)

    def test_confidence_clamps_at_lower_bound(self, mock_seeded):
        store, pid = mock_seeded
        rec = _make_fact(store, pid)
        for _ in range(4):
            result = store.record_feedback(rec["record_id"], "wrong")
        assert result["confidence"] == pytest.approx(0.0)

    def test_confidence_persisted_on_records_row(self, mock_seeded):
        store, pid = mock_seeded
        rec = _make_fact(store, pid)
        store.record_feedback(rec["record_id"], "correct")
        with store.connect() as conn:
            row = conn.execute(
                "SELECT confidence FROM records WHERE record_id = ?",
                (rec["record_id"],),
            ).fetchone()
        assert row["confidence"] == pytest.approx(0.65)

    def test_note_and_source_session_id_are_persisted(self, mock_seeded):
        store, pid = mock_seeded
        rec = _make_fact(store, pid)
        store.record_feedback(
            rec["record_id"],
            "correct",
            note="Confirmed during incident review",
            source_session_id="sess_eval",
        )
        events = store.list_feedback(rec["record_id"])
        assert len(events) == 1
        assert events[0]["signal"] == "correct"
        assert events[0]["note"] == "Confirmed during incident review"
        assert events[0]["source_session_id"] == "sess_eval"
        assert events[0]["record_id"] == rec["record_id"]
        assert events[0]["created_at"]

    def test_invalid_signal_raises_before_touching_record(self, mock_seeded):
        store, pid = mock_seeded
        rec = _make_fact(store, pid)
        with pytest.raises(ValueError, match="invalid_feedback_signal:bogus"):
            store.record_feedback(rec["record_id"], "bogus")
        # Confidence must be untouched by a rejected signal.
        refreshed = store.fetch_record(rec["record_id"])
        assert refreshed["confidence"] == pytest.approx(0.5)
        assert store.list_feedback(rec["record_id"]) == []

    def test_invalid_signal_checked_before_record_existence(self, mock_seeded):
        store, _pid = mock_seeded
        with pytest.raises(ValueError, match="invalid_feedback_signal:bogus"):
            store.record_feedback("rec_does_not_exist", "bogus")

    def test_unknown_record_raises(self, mock_seeded):
        store, _pid = mock_seeded
        with pytest.raises(ValueError, match="record_not_found:rec_missing"):
            store.record_feedback("rec_missing", "correct")

    def test_does_not_add_record_version_row(self, mock_seeded):
        store, pid = mock_seeded
        rec = _make_fact(store, pid)
        with store.connect() as conn:
            before = conn.execute(
                "SELECT COUNT(*) FROM record_versions WHERE record_id = ?",
                (rec["record_id"],),
            ).fetchone()[0]

        store.record_feedback(rec["record_id"], "correct")

        with store.connect() as conn:
            after = conn.execute(
                "SELECT COUNT(*) FROM record_versions WHERE record_id = ?",
                (rec["record_id"],),
            ).fetchone()[0]
        assert before == after == 1

    def test_does_not_bump_records_index_generation(self, mock_seeded):
        store, pid = mock_seeded
        rec = _make_fact(store, pid)
        with store.connect() as conn:
            generation_before = store._records_index_generation(conn)

        store.record_feedback(rec["record_id"], "correct")

        with store.connect() as conn:
            generation_after = store._records_index_generation(conn)
        assert generation_before == generation_after


# ---------------------------------------------------------------------------
# store.py: regression tests for the reviewer-confirmed 0.0-confidence
# corruption and the record_feedback read-modify-write race.
# ---------------------------------------------------------------------------


class TestConfidenceZeroFloorRegression:
    """Regression tests for the `... or DEFAULT_RECORD_CONFIDENCE` bug.

    `_record_row_to_dict` and `record_feedback` used to read a record's
    confidence with a plain `or DEFAULT_RECORD_CONFIDENCE` fallback, which
    treats a genuinely earned `0.0` as falsy and silently substitutes `0.5`.
    That corrupted every reader built on `_record_row_to_dict` (`fetch_record`,
    `query`) once a record's confidence reached the true floor, and it fed a
    phantom `0.5` baseline into the *next* `record_feedback` call instead of
    the real `0.0`. These tests drive a record to the true floor and assert
    every reader -- and the next feedback computation -- sees `0.0`, not `0.5`.
    """

    def test_five_consecutive_wrong_signals_clamp_and_stay_at_floor(
        self, mock_seeded
    ):
        """Reproduces the reviewer's exact 5-call trace at the fixed floor."""
        store, pid = mock_seeded
        rec = _make_fact(store, pid)

        confidences = [
            store.record_feedback(rec["record_id"], "wrong")["confidence"]
            for _ in range(5)
        ]

        # Buggy behavior oscillated forever: [0.25, 0.0, 0.25, 0.0, 0.25].
        # Correct behavior clamps at the floor and stays there.
        assert confidences == pytest.approx([0.25, 0.0, 0.0, 0.0, 0.0])

    def test_fetch_record_reads_back_true_zero_not_phantom_default(
        self, mock_seeded
    ):
        """`fetch_record` must report an earned 0.0, not the 0.5 default."""
        store, pid = mock_seeded
        rec = _make_fact(store, pid)
        store.record_feedback(rec["record_id"], "wrong")
        store.record_feedback(rec["record_id"], "wrong")  # 0.5 -> 0.25 -> 0.0

        refreshed = store.fetch_record(rec["record_id"])

        assert refreshed["confidence"] == pytest.approx(0.0)

    def test_query_records_list_reads_back_true_zero_not_phantom_default(
        self, mock_seeded
    ):
        """`query(records, list)` (CLI/HTTP/MCP list path) must see the real 0.0."""
        store, pid = mock_seeded
        rec = _make_fact(store, pid)
        store.record_feedback(rec["record_id"], "wrong")
        store.record_feedback(rec["record_id"], "wrong")  # 0.5 -> 0.25 -> 0.0

        payload = store.query(entity="records", mode="list", project_ids=[pid])
        matches = [
            row for row in payload["rows"] if row["record_id"] == rec["record_id"]
        ]

        assert len(matches) == 1
        assert matches[0]["confidence"] == pytest.approx(0.0)

    def test_feedback_after_floor_recomputes_from_true_zero_not_phantom_half(
        self, mock_seeded
    ):
        """The next feedback call after the floor must recompute from 0.0."""
        store, pid = mock_seeded
        rec = _make_fact(store, pid)
        store.record_feedback(rec["record_id"], "wrong")
        store.record_feedback(rec["record_id"], "wrong")  # 0.5 -> 0.25 -> 0.0
        assert store.fetch_record(rec["record_id"])["confidence"] == pytest.approx(0.0)

        # A phantom 0.5 baseline would land this on 0.65 instead of 0.15.
        result = store.record_feedback(rec["record_id"], "correct")

        assert result["confidence"] == pytest.approx(0.15)

    def test_record_feedback_does_not_read_current_confidence_via_fetch_record(
        self, mock_seeded, monkeypatch
    ):
        """Regression test for the read-modify-write TOCTOU race.

        The current-confidence read must happen on the same locked
        (`BEGIN IMMEDIATE`) connection as the INSERT+UPDATE, not via a
        separate `fetch_record()` call that opens its own unlocked
        connection/transaction beforehand -- otherwise two concurrent
        `record_feedback` calls for the same record can both read the same
        stale confidence and the second writer silently clobbers the first.
        """
        store, pid = mock_seeded
        rec = _make_fact(store, pid)
        original_fetch_record = store.fetch_record
        calls = []

        def spying_fetch_record(*args, **kwargs):
            calls.append((args, kwargs))
            return original_fetch_record(*args, **kwargs)

        monkeypatch.setattr(store, "fetch_record", spying_fetch_record)

        store.record_feedback(rec["record_id"], "correct")

        assert calls == []

    def test_record_feedback_reads_and_writes_confidence_in_one_transaction(
        self, mock_seeded, monkeypatch
    ):
        """A second, structural check on the same TOCTOU fix: exactly one
        connection/transaction is opened for the read-modify-write itself
        (a second connection is opened by the unconditional `self.initialize()`
        call at the top of `record_feedback`, which is unrelated to this race).
        """
        store, pid = mock_seeded
        rec = _make_fact(store, pid)
        original_connect = store.connect
        calls = []

        @contextmanager
        def counting_connect():
            calls.append(1)
            with original_connect() as conn:
                yield conn

        monkeypatch.setattr(store, "connect", counting_connect)

        store.record_feedback(rec["record_id"], "correct")

        assert len(calls) == 2


# ---------------------------------------------------------------------------
# store.py: ContextStore.list_feedback
# ---------------------------------------------------------------------------


class TestListFeedback:
    """Tests for ContextStore.list_feedback."""

    def test_empty_when_no_feedback_recorded(self, mock_seeded):
        store, pid = mock_seeded
        rec = _make_fact(store, pid)
        assert store.list_feedback(rec["record_id"]) == []

    def test_returns_events_oldest_first(self, mock_seeded):
        store, pid = mock_seeded
        rec = _make_fact(store, pid)
        store.record_feedback(rec["record_id"], "used")
        store.record_feedback(rec["record_id"], "correct")
        store.record_feedback(rec["record_id"], "wrong")

        events = store.list_feedback(rec["record_id"])

        assert [event["signal"] for event in events] == ["used", "correct", "wrong"]

    def test_scoped_to_one_record(self, mock_seeded):
        store, pid = mock_seeded
        rec_a = _make_fact(store, pid, title="Fact A")
        rec_b = _make_fact(store, pid, title="Fact B")
        store.record_feedback(rec_a["record_id"], "correct")
        store.record_feedback(rec_b["record_id"], "wrong")

        events_a = store.list_feedback(rec_a["record_id"])
        events_b = store.list_feedback(rec_b["record_id"])

        assert [event["record_id"] for event in events_a] == [rec_a["record_id"]]
        assert [event["record_id"] for event in events_b] == [rec_b["record_id"]]
        assert events_a[0]["signal"] == "correct"
        assert events_b[0]["signal"] == "wrong"
