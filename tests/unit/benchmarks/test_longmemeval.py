"""Unit tests for the LongMemEval-S benchmark helpers."""

from __future__ import annotations

import math
import json
from pathlib import Path

import pytest

from benchmarks.lerim_evidence.longmemeval import (
    LongMemEvalEntry,
    chunk_session_to_text,
    episode_fields_from_transcript,
    filter_entries,
    load_dataset,
    mrr,
    ndcg,
    nearest_rank_percentile,
    recall_any,
)
from lerim.context.spec import (
    MAX_EPISODE_BODY_CHARS,
    MAX_EPISODE_OUTCOMES_CHARS,
    MAX_EPISODE_USER_INTENT_CHARS,
    MAX_EPISODE_WHAT_HAPPENED_CHARS,
)


def test_recall_any_matches_retrieval_shape() -> None:
    """Recall is one when any gold session is present in the top-k window."""
    retrieved = ["s1", "s2", "gold", "s4"]
    assert recall_any(retrieved, ["gold"], 2) == 0.0
    assert recall_any(retrieved, ["gold"], 3) == 1.0
    assert recall_any(retrieved, ["missing", "s2"], 2) == 1.0


def test_rank_metrics() -> None:
    """NDCG and MRR reward earlier matching sessions."""
    retrieved = ["wrong", "gold_b", "wrong_2", "gold_a"]
    gold = {"gold_a", "gold_b"}
    assert mrr(retrieved, gold) == pytest.approx(0.5)
    assert ndcg(retrieved, gold, 4) == pytest.approx(
        ((1 / math.log2(3)) + (1 / math.log2(5))) / (1 + (1 / math.log2(3)))
    )


def test_chunk_session_to_text_uses_role_content_lines() -> None:
    """Session chunks use a compact role/content transcript shape."""
    text = chunk_session_to_text(
        [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
            {"role": "tool", "content": ""},
        ]
    )
    assert text == "user: hello\nassistant: hi"


def test_episode_fields_respect_lerim_schema_limits() -> None:
    """Benchmark transcript mapping stays inside canonical Lerim episode limits."""
    fields = episode_fields_from_transcript(
        transcript="abcdef " * 1000,
        session_id="session-1",
        turn_count=2,
    )
    assert len(fields["body"]) <= MAX_EPISODE_BODY_CHARS
    assert len(fields["user_intent"]) <= MAX_EPISODE_USER_INTENT_CHARS
    assert len(fields["what_happened"]) <= MAX_EPISODE_WHAT_HAPPENED_CHARS
    assert len(fields["outcomes"]) <= MAX_EPISODE_OUTCOMES_CHARS


def test_filter_entries_excludes_abstention_and_type_filters() -> None:
    """Dataset filtering excludes abstention rows and unwanted question types."""
    keep = LongMemEvalEntry(
        question_id="q1",
        question_type="single-session-user",
        question="question",
        question_date="date",
        answer="answer",
        answer_session_ids=["s1"],
        haystack_dates=["date"],
        haystack_session_ids=["s1"],
        haystack_sessions=[[{"role": "user", "content": "hello"}]],
    )
    abstain = LongMemEvalEntry(
        question_id="q2",
        question_type="multi-session_abs",
        question="question",
        question_date="date",
        answer="answer",
        answer_session_ids=["s2"],
        haystack_dates=["date"],
        haystack_session_ids=["s2"],
        haystack_sessions=[[{"role": "user", "content": "hello"}]],
    )
    other = LongMemEvalEntry(
        question_id="q3",
        question_type="temporal-reasoning",
        question="question",
        question_date="date",
        answer="answer",
        answer_session_ids=["s3"],
        haystack_dates=["date"],
        haystack_session_ids=["s3"],
        haystack_sessions=[[{"role": "user", "content": "hello"}]],
    )
    filtered, abstention_count = filter_entries(
        [keep, abstain, other],
        question_type="single-session-user",
    )
    assert filtered == [keep]
    assert abstention_count == 1


def test_nearest_rank_percentile() -> None:
    """Percentiles use the nearest-rank method used by benchmark harnesses."""
    assert nearest_rank_percentile([10, 20, 30, 40], 50) == 20
    assert nearest_rank_percentile([10, 20, 30, 40], 99) == 40
    assert nearest_rank_percentile([], 95) == 0.0


def _write_dataset(tmp_path: Path, row: dict[str, object]) -> Path:
    """Write a one-row LongMemEval fixture."""
    path = tmp_path / "longmemeval.json"
    path.write_text(json.dumps([row]), encoding="utf-8")
    return path


def _valid_row() -> dict[str, object]:
    """Return a minimal valid LongMemEval row."""
    return {
        "question_id": "q1",
        "question_type": "single-session-user",
        "question": "What happened?",
        "question_date": "2026-05-19",
        "answer": "A thing happened.",
        "answer_session_ids": ["s1"],
        "haystack_dates": ["2026-05-18"],
        "haystack_session_ids": ["s1"],
        "haystack_sessions": [[{"role": "user", "content": "hello"}]],
    }


def test_load_dataset_rejects_string_answer_session_ids(tmp_path: Path) -> None:
    """Dataset loading rejects scalar answer_session_ids instead of iterating chars."""
    row = _valid_row()
    row["answer_session_ids"] = "s1"

    with pytest.raises(
        ValueError,
        match="longmemeval_entry_field_must_be_list:0:answer_session_ids",
    ):
        load_dataset(_write_dataset(tmp_path, row))


def test_load_dataset_rejects_non_list_haystack_sessions(tmp_path: Path) -> None:
    """Dataset loading rejects malformed haystack_sessions."""
    row = _valid_row()
    row["haystack_sessions"] = "not-a-list"

    with pytest.raises(
        ValueError,
        match="longmemeval_entry_field_must_be_list:0:haystack_sessions",
    ):
        load_dataset(_write_dataset(tmp_path, row))


def test_load_dataset_rejects_mismatched_haystack_lengths(tmp_path: Path) -> None:
    """Dataset loading requires aligned haystack metadata arrays."""
    row = _valid_row()
    row["haystack_session_ids"] = ["s1", "s2"]

    with pytest.raises(
        ValueError,
        match="longmemeval_entry_haystack_length_mismatch:0",
    ):
        load_dataset(_write_dataset(tmp_path, row))
