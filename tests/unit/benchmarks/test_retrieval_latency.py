"""Unit tests for retrieval latency benchmark helpers."""

from __future__ import annotations

import pytest

from benchmarks.lerim_evidence.retrieval_latency import parse_sizes, summarize_latency


def test_parse_sizes_sorts_and_deduplicates() -> None:
    """Corpus-size parsing accepts comma-separated positive integers."""
    assert parse_sizes("1000,100,100") == [100, 1000]


def test_parse_sizes_rejects_empty_or_nonpositive() -> None:
    """Latency benchmark sizes must be explicit positive integers."""
    with pytest.raises(ValueError):
        parse_sizes("")
    with pytest.raises(ValueError):
        parse_sizes("100,0")


def test_summarize_latency_reports_tail_metrics() -> None:
    """Latency summary returns nearest-rank tail metrics and hit counts."""
    rows = [
        {"latency_ms": 3.0, "hit_count": 10},
        {"latency_ms": 1.0, "hit_count": 8},
        {"latency_ms": 2.0, "hit_count": 9},
    ]
    result = summarize_latency(rows)
    assert result["ops"] == 3
    assert result["p50_ms"] == 2.0
    assert result["p99_ms"] == 3.0
    assert result["avg_hit_count"] == 9.0
