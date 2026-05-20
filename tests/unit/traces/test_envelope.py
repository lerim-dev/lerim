"""Tests for generic trace envelope normalization."""

from __future__ import annotations

import json

import pytest

from lerim.traces.envelope import load_generic_trace, write_compact_trace


def test_load_generic_trace_reads_jsonl_events(tmp_path):
    """JSONL events become canonical compact trace entries."""
    trace_path = tmp_path / "trace.jsonl"
    trace_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "role": "customer",
                        "content": "I need help with billing.",
                        "timestamp": "2026-05-15T10:00:00Z",
                    }
                ),
                json.dumps(
                    {
                        "role": "agent",
                        "content": "I checked the invoice.",
                        "timestamp": "2026-05-15T10:01:00Z",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    trace = load_generic_trace(trace_path)

    assert trace.trace_id.startswith("trace_")
    assert trace.started_at == "2026-05-15T10:00:00Z"
    assert trace.message_count == 2
    assert trace.events[0]["type"] == "user"
    assert trace.events[1]["type"] == "assistant"


def test_load_generic_trace_reads_json_object_messages(tmp_path):
    """A JSON object with a messages list is normalized as events."""
    trace_path = tmp_path / "trace.json"
    trace_path.write_text(
        json.dumps(
            {
                "messages": [
                    {"role": "user", "message": {"content": "find flights"}},
                    {"role": "assistant", "message": {"content": "found options"}},
                ]
            }
        ),
        encoding="utf-8",
    )

    trace = load_generic_trace(trace_path)

    assert [event["message"]["content"] for event in trace.events] == [
        "find flights",
        "found options",
    ]


def test_load_generic_trace_uses_content_based_trace_id(tmp_path):
    """Equivalent payloads keep the same trace id across file paths."""
    first = tmp_path / "first.jsonl"
    second = tmp_path / "nested" / "second.jsonl"
    second.parent.mkdir()
    payload = '{"role":"user","content":"stable event"}\n'
    first.write_text(payload, encoding="utf-8")
    second.write_text(payload, encoding="utf-8")

    first_trace = load_generic_trace(first)
    second_trace = load_generic_trace(second)

    assert first_trace.trace_id == second_trace.trace_id
    assert first_trace.content_hash == second_trace.content_hash


def test_load_generic_trace_preserves_wrapper_metadata(tmp_path):
    """Wrapper metadata is preserved separately from message events."""
    trace_path = tmp_path / "trace.json"
    trace_path.write_text(
        json.dumps(
            {
                "session_id": "sess-wrapper",
                "source_name": "support-bot",
                "metadata": {"cwd": "/tmp/repo", "ticket": "T-123"},
                "messages": [{"role": "user", "content": "help"}],
            }
        ),
        encoding="utf-8",
    )

    trace = load_generic_trace(trace_path)

    assert trace.session_id == "sess-wrapper"
    assert trace.metadata == {
        "cwd": "/tmp/repo",
        "ticket": "T-123",
        "session_id": "sess-wrapper",
        "source_name": "support-bot",
    }


def test_load_generic_trace_wraps_raw_text(tmp_path):
    """Raw text traces are preserved as one user message."""
    trace_path = tmp_path / "trace.txt"
    trace_path.write_text("raw transcript text", encoding="utf-8")

    trace = load_generic_trace(trace_path)

    assert trace.message_count == 1
    assert trace.events[0]["type"] == "user"
    assert trace.events[0]["message"]["content"] == "raw transcript text"


def test_load_generic_trace_rejects_empty_file(tmp_path):
    """Empty trace imports fail before the extraction path spends model calls."""
    trace_path = tmp_path / "empty.jsonl"
    trace_path.write_text(" \n\t\n", encoding="utf-8")

    with pytest.raises(ValueError, match="trace file is empty"):
        load_generic_trace(trace_path)


def test_write_compact_trace_outputs_jsonl(tmp_path):
    """Normalized traces are written as newline-delimited canonical JSON."""
    source = tmp_path / "trace.jsonl"
    source.write_text('{"role":"user","content":"hello"}\n', encoding="utf-8")
    trace = load_generic_trace(source)
    destination = tmp_path / "normalized" / "trace.jsonl"

    write_compact_trace(trace, destination)

    lines = destination.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["message"]["content"] == "hello"
