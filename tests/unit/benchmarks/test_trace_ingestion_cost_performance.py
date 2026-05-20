"""Unit tests for trace-ingestion cost/performance benchmark helpers."""

from __future__ import annotations

from benchmarks.lerim_evidence.trace_ingestion_cost_performance import summarize


def test_summarize_reports_measured_calls_and_unavailable_cost() -> None:
    """Summary keeps measured LLM calls separate from unavailable provider cost."""
    rows = [
        {
            "status": "pass",
            "ingestion_ms": 100.0,
            "llm_calls": 5,
            "db_size_delta_bytes": 1000,
            "durable_record_count": 1,
        },
        {
            "status": "pass",
            "ingestion_ms": 200.0,
            "llm_calls": 7,
            "db_size_delta_bytes": 3000,
            "durable_record_count": 0,
        },
    ]

    result = summarize(rows, baseline_schema_bytes=512)

    headline = result["headline"]
    assert headline["trace_count"] == 2
    assert headline["avg_ingestion_ms"] == 150.0
    assert headline["avg_llm_calls_per_trace"] == 6.0
    assert headline["total_llm_calls"] == 12
    assert headline["avg_db_size_delta_bytes"] == 2000.0
    assert headline["baseline_schema_bytes"] == 512
    assert headline["cost_usd_available"] is False
    assert headline["avg_cost_usd_per_trace"] is None
