"""Hybrid context retrieval helpers for the SQLite context store."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import sqlite_vec

from lerim.config.settings import get_config
from lerim.context.roles import DEFAULT_RECORD_ROLE
from lerim.context.spec import DEFAULT_RECORD_CONFIDENCE

RRF_K = 60
"""Reciprocal Rank Fusion damping constant.

Standard RRF practice (Cormack, Clarke & Buettcher, 2009) uses K=60: large enough
that the score gap between adjacent top ranks stays gentle (1/61 vs 1/62, about a
1.6% step), so the fused order reflects broad agreement between the semantic and
lexical retrievers rather than one retriever's noisy rank-1 pick. The previous
K=2 made that same step (1/3 vs 1/4, a 33% jump) so steep that whichever
retriever happened to rank a record #1 could dominate the fused order on its own.
"""
DEFAULT_SEMANTIC_RRF_WEIGHT = 0.7
DEFAULT_LEXICAL_RRF_WEIGHT = 0.3

CONFIDENCE_MULTIPLIER_FLOOR = 0.5
CONFIDENCE_MULTIPLIER_CEILING = 1.5
"""Bounds of the earned-confidence multiplier applied to a fused RRF score.

Confidence lives in [0, 1] with a neutral default of 0.5 (see
lerim.context.spec.DEFAULT_RECORD_CONFIDENCE). Mapping confidence linearly onto
[0.5, 1.5] means a record at the default confidence leaves its fused score
unchanged (multiplier 1.0), a fully-confirmed record (confidence 1.0) is boosted
up to 1.5x, and a record repeatedly marked wrong (confidence 0.0) is discounted
to 0.5x. Confidence can therefore reorder close matches but cannot, by itself,
zero out or invert a materially stronger rank signal.
"""

RECENCY_BOOST_WEIGHT = 0.1
"""Mild recency boost, capped at +/-10% of a candidate's fused score.

Recency is normalized *within one query's fused candidates* (the newest
candidate gets the full +RECENCY_BOOST_WEIGHT, the oldest the full
-RECENCY_BOOST_WEIGHT) rather than compared against wall-clock age. That keeps
the boost meaningful whether the whole corpus is a day old or a year old. It is
intentionally small so it only nudges close ties toward the newer record.
"""

RELEVANCE_FLOOR_REFERENCE_RANK = 40
"""Shortlist depth used only to calibrate RELEVANCE_FLOOR, not a query limit.

Matches the shipped default `semantic_shortlist_size` / `lexical_shortlist_size`
(config/default.toml). `search_records` fetches at least this many candidates
per retriever for the shipped default query `limit` of 8 (it requests
`max(limit * 3, shortlist_size)`); a larger caller-supplied `limit`, or extra
kind/role/status/valid_at filters, only deepens the real shortlist further.
Calibrating against this realistic depth -- rather than an idealized rank-1
candidate -- is what gives RELEVANCE_FLOOR real teeth. See RELEVANCE_FLOOR.
"""

RELEVANCE_FLOOR_SAFETY_MARGIN = 1.25
"""Multiplier over the worst-case score RELEVANCE_FLOOR is calibrated against,
so that exact worst case lands strictly under the floor rather than exactly on
the (inclusive) boundary.
"""

RELEVANCE_FLOOR = RELEVANCE_FLOOR_SAFETY_MARGIN * (
    DEFAULT_SEMANTIC_RRF_WEIGHT
    / (RRF_K + RELEVANCE_FLOOR_REFERENCE_RANK)
    * CONFIDENCE_MULTIPLIER_FLOOR
    * (1.0 - RECENCY_BOOST_WEIGHT)
)
"""Minimum blended (RRF x confidence x recency) score required to appear at all.

Nearest-neighbor search always returns *something*, however distant from the
query, so without a floor `search_records` would keep padding results out to
`limit` with candidates nobody actually wants. When no fused candidate clears
this conservative bar, `search_records` returns fewer results, or none, instead
of forcing top-k.

Calibrated against the weakest realistic survivor of a full shortlist: a
candidate ranked dead last (RELEVANCE_FLOOR_REFERENCE_RANK) in only the
higher-weighted retriever (DEFAULT_SEMANTIC_RRF_WEIGHT -- the harder of the two
retrievers to exclude, since it counts for more) that has also been repeatedly
marked wrong (confidence at CONFIDENCE_MULTIPLIER_FLOOR) and is the most stale
record in its batch (recency at its floor multiplier). An earlier version of
this floor was set as a small fraction (5%) of an idealized rank-1-in-both
ceiling instead; because RRF's rank-based score decays gently by design (see
RRF_K), that ceiling was so much larger than realistic shortlist-tail scores
that the floor could never actually exclude anything reachable at the shipped
default shortlist depth, no matter how weak, unconfirmed, or stale. A
candidate that is merely unconfirmed (default confidence) or merely old, but
not both weak-ranked and actively discredited/stale, still clears this floor
comfortably -- see TestRelevanceFloorAtRealisticShortlistDepth in
test_retrieval.py.
"""


@dataclass(frozen=True)
class SearchHit:
    """Compact retrieval hit returned by hybrid search."""

    record_id: str
    project_id: str
    kind: str
    title: str
    body: str
    status: str
    created_at: str
    updated_at: str
    valid_from: str
    valid_until: str | None
    score: float
    sources: list[str]
    decision: str | None = None
    why: str | None = None
    alternatives: str | None = None
    consequences: str | None = None
    user_intent: str | None = None
    what_happened: str | None = None
    outcomes: str | None = None
    record_role: str = DEFAULT_RECORD_ROLE
    role_payload: str | None = None
    confidence: float = DEFAULT_RECORD_CONFIDENCE


def search_records(
    store: Any,
    *,
    project_ids: list[str] | None,
    query: str,
    kind_filters: list[str] | None = None,
    role_filters: list[str] | None = None,
    statuses: list[str] | None = None,
    valid_at: str | None = None,
    include_archived: bool = False,
    limit: int = 8,
) -> list[SearchHit]:
    """Run hybrid retrieval over records for one context store.

    Candidate metadata (confidence, updated_at) is fetched for the FULL fused
    candidate set before any `limit` slicing happens, so blend_confidence_and_recency
    and apply_relevance_floor can rerank -- and trim -- the whole set first.
    Recency uses `updated_at` rather than `valid_from`: record_feedback (earned
    confidence) intentionally leaves `updated_at` untouched, so it stays a clean
    signal of when the record's own content last changed, independent of
    confidence, rather than of when it first became true.
    """
    config = get_config()
    with store.connect() as conn:
        fts_available = True
        try:
            store._prepare_search_fts(conn)
        except sqlite3.OperationalError:
            conn.rollback()
            fts_available = False
        store._prepare_search_embeddings(conn)
        conn.commit()
        conn.execute("BEGIN")
        semantic_rows = semantic_candidates(
            store,
            project_ids=project_ids,
            query=query,
            kind_filters=kind_filters,
            role_filters=role_filters,
            statuses=statuses,
            valid_at=valid_at,
            include_archived=include_archived,
            limit=max(limit * 3, config.semantic_shortlist_size),
            conn=conn,
        )
        lexical_rows: list[tuple[str, float]] = []
        if fts_available:
            try:
                lexical_rows = lexical_candidates(
                    store,
                    project_ids=project_ids,
                    query=query,
                    kind_filters=kind_filters,
                    role_filters=role_filters,
                    statuses=statuses,
                    valid_at=valid_at,
                    include_archived=include_archived,
                    limit=max(limit * 3, config.lexical_shortlist_size),
                    conn=conn,
                )
            except sqlite3.OperationalError:
                lexical_rows = []
        combined = rrf_fuse(
            semantic_rows=semantic_rows,
            lexical_rows=lexical_rows,
            semantic_weight=DEFAULT_SEMANTIC_RRF_WEIGHT,
            lexical_weight=DEFAULT_LEXICAL_RRF_WEIGHT,
        )
        if not combined:
            return []
        # Fetch metadata for every fused candidate (not just the top `limit`) so
        # reranking below sees the full picture before anything is sliced away.
        candidate_ids = [record_id for record_id, _score, _sources in combined]
        placeholders = ", ".join("?" for _ in candidate_ids)
        rows = conn.execute(
            f"SELECT * FROM records WHERE record_id IN ({placeholders})",
            tuple(candidate_ids),
        ).fetchall()
    row_map = {str(row["record_id"]): row for row in rows}
    confidence_by_id = {
        record_id: float(row["confidence"]) for record_id, row in row_map.items()
    }
    updated_at_by_id = {
        record_id: str(row["updated_at"]) for record_id, row in row_map.items()
    }
    reranked = blend_confidence_and_recency(
        combined,
        confidence_by_id=confidence_by_id,
        updated_at_by_id=updated_at_by_id,
    )
    reranked = apply_relevance_floor(reranked)
    hits: list[SearchHit] = []
    for record_id, score, sources in reranked:
        row = row_map.get(record_id)
        if row is None:
            continue
        hits.append(
            SearchHit(
                record_id=record_id,
                project_id=str(row["project_id"]),
                kind=str(row["kind"]),
                record_role=str(row["record_role"]),
                title=str(row["title"]),
                body=str(row["body"]),
                role_payload=row["role_payload"],
                decision=row["decision"],
                why=row["why"],
                alternatives=row["alternatives"],
                consequences=row["consequences"],
                user_intent=row["user_intent"],
                what_happened=row["what_happened"],
                outcomes=row["outcomes"],
                status=str(row["status"]),
                created_at=str(row["created_at"]),
                updated_at=str(row["updated_at"]),
                valid_from=str(row["valid_from"]),
                valid_until=row["valid_until"],
                score=score,
                confidence=confidence_by_id.get(record_id, DEFAULT_RECORD_CONFIDENCE),
                sources=sources,
            )
        )
        if len(hits) >= limit:
            break
    return hits


def semantic_candidates(
    store: Any,
    *,
    project_ids: list[str] | None,
    query: str,
    kind_filters: list[str] | None,
    statuses: list[str] | None,
    valid_at: str | None,
    include_archived: bool,
    limit: int,
    role_filters: list[str] | None = None,
    conn: sqlite3.Connection | None = None,
) -> list[tuple[str, float]]:
    """Return ranked semantic candidates from sqlite-vec nearest neighbors."""
    provider = store.embedding_provider()
    query_vec = sqlite_vec.serialize_float32(provider.embed_query(query))
    filter_sql, params = store._build_record_filter_sql(
        project_ids=project_ids,
        kind_filters=kind_filters,
        role_filters=role_filters,
        statuses=statuses,
        source_session_id=None,
        created_since=None,
        created_until=None,
        updated_since=None,
        updated_until=None,
        valid_at=valid_at,
        include_archived=include_archived,
        table_alias="records",
    )
    vector_filter_sql = ""
    vector_filter_params: list[Any] = []
    if project_ids and len(project_ids) == 1:
        vector_filter_sql = " AND record_embeddings.project_id = ?"
        vector_filter_params.append(project_ids[0])

    def read_candidates(active_conn: sqlite3.Connection) -> list[sqlite3.Row]:
        """Read filtered semantic candidates from one active connection."""
        max_candidates = int(
            active_conn.execute(
                f"SELECT COUNT(*) FROM record_embeddings WHERE 1=1{vector_filter_sql}",
                tuple(vector_filter_params),
            ).fetchone()[0]
        )
        candidate_limit = min(max_candidates, max(int(limit), 25))
        if project_ids or kind_filters or role_filters or statuses or valid_at or include_archived:
            candidate_limit = min(max_candidates, max(candidate_limit, int(limit) * 4))
        rows: list[sqlite3.Row] = []
        while candidate_limit > 0:
            rows = active_conn.execute(
                f"""
                SELECT records.record_id, record_embeddings.distance
                FROM record_embeddings
                JOIN records ON records.record_id = record_embeddings.record_id
                WHERE record_embeddings.embedding MATCH ?
                  AND record_embeddings.k = ?
                  {vector_filter_sql}
                  AND {filter_sql}
                ORDER BY record_embeddings.distance ASC
                LIMIT ?
                """,
                tuple([query_vec, candidate_limit] + vector_filter_params + params + [candidate_limit]),
            ).fetchall()
            if len(rows) >= limit or candidate_limit >= max_candidates:
                break
            candidate_limit = min(max_candidates, max(candidate_limit * 2, candidate_limit + 1))
        return rows

    if conn is None:
        with store.connect() as active_conn:
            store._prepare_search_embeddings(active_conn)
            rows = read_candidates(active_conn)
    else:
        rows = read_candidates(conn)
    return [(str(row["record_id"]), float(row["distance"])) for row in rows]


def lexical_candidates(
    store: Any,
    *,
    project_ids: list[str] | None,
    query: str,
    kind_filters: list[str] | None,
    statuses: list[str] | None,
    valid_at: str | None,
    include_archived: bool,
    limit: int,
    role_filters: list[str] | None = None,
    conn: sqlite3.Connection | None = None,
) -> list[tuple[str, float]]:
    """Return ranked lexical candidates from SQLite FTS."""
    compiled_query = compile_safe_fts_query(query)
    if not compiled_query:
        return []
    filter_sql, params = store._build_record_filter_sql(
        project_ids=project_ids,
        kind_filters=kind_filters,
        role_filters=role_filters,
        statuses=statuses,
        source_session_id=None,
        created_since=None,
        created_until=None,
        updated_since=None,
        updated_until=None,
        valid_at=valid_at,
        include_archived=include_archived,
        table_alias="records",
    )

    def read_candidates(active_conn: sqlite3.Connection) -> list[sqlite3.Row]:
        """Read filtered lexical candidates from one active connection."""
        return active_conn.execute(
            f"""
            SELECT records.record_id, bm25(records_fts) AS rank_score
            FROM records_fts
            JOIN records ON records.record_id = records_fts.record_id
            WHERE records_fts MATCH ? AND {filter_sql}
            ORDER BY rank_score ASC
            LIMIT ?
            """,
            tuple([compiled_query] + params + [limit]),
        ).fetchall()

    if conn is None:
        with store.connect() as active_conn:
            store._prepare_search_fts(active_conn)
            rows = read_candidates(active_conn)
    else:
        rows = read_candidates(conn)
    return [(str(row["record_id"]), float(row["rank_score"])) for row in rows]


def rrf_fuse(
    *,
    semantic_rows: list[tuple[str, float]],
    lexical_rows: list[tuple[str, float]],
    semantic_weight: float = 1.0,
    lexical_weight: float = 1.0,
) -> list[tuple[str, float, list[str]]]:
    """Fuse ranked lists with Reciprocal Rank Fusion."""
    scores: dict[str, float] = {}
    sources: dict[str, set[str]] = {}
    for rank, (record_id, _score) in enumerate(semantic_rows, start=1):
        scores[record_id] = scores.get(record_id, 0.0) + semantic_weight / (RRF_K + rank)
        sources.setdefault(record_id, set()).add("semantic")
    for rank, (record_id, _score) in enumerate(lexical_rows, start=1):
        scores[record_id] = scores.get(record_id, 0.0) + lexical_weight / (RRF_K + rank)
        sources.setdefault(record_id, set()).add("fts")
    combined = [
        (record_id, score, sorted(sources.get(record_id, set())))
        for record_id, score in scores.items()
    ]
    combined.sort(key=lambda item: item[1], reverse=True)
    return combined


def blend_confidence_and_recency(
    combined: list[tuple[str, float, list[str]]],
    *,
    confidence_by_id: dict[str, float],
    updated_at_by_id: dict[str, str],
) -> list[tuple[str, float, list[str]]]:
    """Rerank fused RRF candidates by folding in earned confidence and recency.

    Call this over the FULL fused candidate set, before any `limit` slicing, so a
    lower-ranked but well-confirmed, recently-touched record can out-rank a
    higher-ranked one that has been discredited or gone stale. Each fused RRF
    score is scaled by a confidence multiplier (CONFIDENCE_MULTIPLIER_FLOOR..
    CONFIDENCE_MULTIPLIER_CEILING) and a mild, batch-relative recency multiplier
    (+/-RECENCY_BOOST_WEIGHT), then the list is re-sorted descending. A candidate
    missing from either metadata map is treated as neutral rather than penalized.
    """
    recency_multipliers = _recency_multipliers(updated_at_by_id)
    blended = [
        (
            record_id,
            rrf_score
            * _confidence_multiplier(confidence_by_id.get(record_id, DEFAULT_RECORD_CONFIDENCE))
            * recency_multipliers.get(record_id, 1.0),
            sources,
        )
        for record_id, rrf_score, sources in combined
    ]
    blended.sort(key=lambda item: item[1], reverse=True)
    return blended


def apply_relevance_floor(
    reranked: list[tuple[str, float, list[str]]],
) -> list[tuple[str, float, list[str]]]:
    """Drop candidates whose blended score falls below RELEVANCE_FLOOR.

    Nearest-neighbor search always returns *something*, however distant from the
    query, so without this floor a caller would keep receiving `limit` results
    even when nothing in the fused set is a real match. Keeps the (already
    descending) ordering of whatever survives.
    """
    return [item for item in reranked if item[1] >= RELEVANCE_FLOOR]


def _confidence_multiplier(confidence: float) -> float:
    """Map earned confidence in [0, 1] onto the confidence score multiplier.

    Confidence is clamped defensively before scaling, so a caller passing an
    out-of-range value degrades to the nearest valid bound instead of inverting
    the ranking.
    """
    clamped = max(0.0, min(1.0, float(confidence)))
    span = CONFIDENCE_MULTIPLIER_CEILING - CONFIDENCE_MULTIPLIER_FLOOR
    return CONFIDENCE_MULTIPLIER_FLOOR + clamped * span


def _recency_multipliers(updated_at_by_id: dict[str, str]) -> dict[str, float]:
    """Return a mild, batch-relative recency multiplier per candidate.

    Recency is normalized against the *other fused candidates in this query*
    (the newest gets the full +RECENCY_BOOST_WEIGHT, the oldest the full
    -RECENCY_BOOST_WEIGHT) rather than against wall-clock age, so the boost
    stays meaningful whether the whole corpus is a day old or a year old.
    Candidates with an unparseable timestamp, and batches with fewer than two
    distinct parseable timestamps to compare, are left neutral (multiplier 1.0).
    """
    parsed: dict[str, datetime] = {}
    for record_id, raw in updated_at_by_id.items():
        parsed_ts = _parse_utc_timestamp(raw)
        if parsed_ts is not None:
            parsed[record_id] = parsed_ts
    multipliers = dict.fromkeys(updated_at_by_id, 1.0)
    if len(parsed) < 2:
        return multipliers
    oldest = min(parsed.values())
    newest = max(parsed.values())
    span_seconds = (newest - oldest).total_seconds()
    if span_seconds <= 0:
        return multipliers
    for record_id, timestamp in parsed.items():
        fraction = (timestamp - oldest).total_seconds() / span_seconds
        multipliers[record_id] = 1.0 + RECENCY_BOOST_WEIGHT * (2 * fraction - 1)
    return multipliers


def _parse_utc_timestamp(raw: str | None) -> datetime | None:
    """Parse one ISO-8601 timestamp into an aware UTC datetime, or None.

    Recency is an advisory ranking input, so a timestamp that fails to parse is
    simply excluded from the recency comparison rather than raising.
    """
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def compile_safe_fts_query(raw: str) -> str | None:
    """Compile free-form text into a conservative SQLite FTS query."""
    if not raw or not raw.strip():
        return None

    normalized_chars: list[str] = []
    for char in raw:
        normalized_chars.append(char if char.isalnum() else " ")
    normalized = "".join(normalized_chars)

    terms: list[str] = []
    seen: set[str] = set()
    for token in normalized.split():
        term = token.strip()
        if not term:
            continue
        lowered = term.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        terms.append(term)
        if len(terms) >= 8:
            break

    if not terms:
        return None
    return " OR ".join(f'"{term}"' for term in terms)
