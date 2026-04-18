"""Unit tests for DB-backed HTTP dashboard helper functions."""

from __future__ import annotations

import json

from lerim.server.httpd import (
    _compute_stats,
    _extract_session_details,
    _parse_int,
    _scope_bounds,
)


def _fake_row(**kwargs) -> dict:
    """Build a dict that mimics one session row for _compute_stats."""
    defaults = {
        "agent_type": "claude",
        "start_time": "2026-02-20T10:00:00Z",
        "status": "completed",
        "message_count": 5,
        "tool_call_count": 2,
        "error_count": 0,
        "total_tokens": 1000,
        "duration_ms": 5000,
        "session_path": "",
    }
    defaults.update(kwargs)
    return defaults


def test_parse_int_valid():
    """_parse_int('42', ...) -> 42."""
    assert _parse_int("42", 0) == 42


def test_parse_int_clamped():
    """_parse_int('1000', max=100) -> 100."""
    assert _parse_int("1000", 0, maximum=100) == 100


def test_parse_int_invalid():
    """_parse_int('abc', default=0) -> 0."""
    assert _parse_int("abc", 0) == 0


def test_scope_bounds_24h():
    """_scope_bounds('today') returns bounds approximately 24h apart."""
    since, until = _scope_bounds("today")
    assert since is not None
    diff = until - since
    assert abs(diff.total_seconds() - 86400) < 60


def test_compute_stats_aggregation():
    """_compute_stats on sample rows returns correct totals."""
    rows = [
        _fake_row(message_count=10, total_tokens=500),
        _fake_row(message_count=5, total_tokens=300, error_count=1),
    ]
    stats = _compute_stats(rows)
    assert stats["totals"]["runs"] == 2
    assert stats["totals"]["messages"] == 15
    assert stats["totals"]["tokens"] == 800
    assert stats["totals"]["runs_with_errors"] == 1
    assert stats["totals"]["unique_tools"] == 0
    assert stats["totals"]["input_tokens"] + stats["totals"]["output_tokens"] == 800
    assert stats["derived"]["avg_messages_per_session"] == 7.5
    assert stats["derived"]["error_rate"] == 50.0
    assert stats["derived"]["duration_data_available"] is True
    assert "by_agent" in stats


def test_extract_session_details_reads_codex_payload_model(tmp_path):
    """_extract_session_details reads model/tool from Codex payload rows."""
    trace = tmp_path / "codex.jsonl"
    rows = [
        {"type": "session_meta", "payload": {"model_provider": "openai"}},
        {
            "type": "event_msg",
            "payload": {
                "type": "agent_message_delta",
                "model": "gpt-5.3-codex",
                "collaboration_mode": {"settings": {"model": "gpt-5.3-codex"}},
            },
        },
        {"type": "response_item", "payload": {"type": "function_call", "name": "Read"}},
    ]
    trace.write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )
    details = _extract_session_details(str(trace))
    assert details["model"] == "gpt-5.3-codex"
    assert details["tools"]["Read"] == 1


def test_extract_session_details_reads_cursor_model(tmp_path):
    """_extract_session_details reads model/tool from Cursor trace rows."""
    trace = tmp_path / "cursor.jsonl"
    rows = [
        {"modelConfig": {"modelName": "composer-1.5"}},
        {"type": "tool_call", "name": "read_file"},
    ]
    trace.write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )
    details = _extract_session_details(str(trace))
    assert details["model"] == "composer-1.5"
    assert details["tools"]["read_file"] == 1
