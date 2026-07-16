"""Unit tests for redaction wiring in lerim.traces.envelope.write_compact_trace.

This custom-import path builds its own canonical JSONL independently of
adapters/common.py's write_session_cache, and previously ran no scrubbing
at all. These tests exercise that specific wiring rather than the
redaction patterns themselves (covered in tests/unit/test_redaction.py).
"""

from __future__ import annotations

import json

from lerim.traces.envelope import NormalizedTrace, write_compact_trace


def _trace_with_content(content: str) -> NormalizedTrace:
    """Build a minimal one-event NormalizedTrace carrying the given content."""
    event = {
        "type": "user",
        "message": {"role": "user", "content": content},
        "timestamp": None,
    }
    return NormalizedTrace(
        trace_id="trace_test",
        events=(event,),
        started_at=None,
        message_count=1,
        content_hash="deadbeefcafefeed",
    )


def test_write_compact_trace_redacts_email(tmp_path):
    """An email address embedded in event content is redacted on write."""
    trace = _trace_with_content("please email ops@example.com about this")
    destination = tmp_path / "normalized" / "trace.jsonl"

    write_compact_trace(trace, destination)

    text = destination.read_text(encoding="utf-8")
    assert "ops@example.com" not in text
    assert "[REDACTED:email]" in text


def test_write_compact_trace_redacts_api_key(tmp_path):
    """An OpenAI-style API key embedded in event content is redacted on write."""
    trace = _trace_with_content("here is my key sk-abcdefghijklmnopqrstuvwx0011")
    destination = tmp_path / "trace.jsonl"

    write_compact_trace(trace, destination)

    text = destination.read_text(encoding="utf-8")
    assert "sk-abcdefghijklmnopqrstuvwx0011" not in text
    assert "[REDACTED:api_key]" in text


def test_write_compact_trace_redacts_private_key_block(tmp_path):
    """A private key PEM block embedded in event content is redacted on write."""
    key_block = (
        "-----BEGIN RSA PRIVATE KEY-----\n"
        "MIIEpAIBAAKCAQEA1234567890abcdefghijklmnop\n"
        "-----END RSA PRIVATE KEY-----"
    )
    trace = _trace_with_content(f"rotate this key:\n{key_block}")
    destination = tmp_path / "trace.jsonl"

    write_compact_trace(trace, destination)

    text = destination.read_text(encoding="utf-8")
    assert "MIIEpAIBAAKCAQEA1234567890abcdefghijklmnop" not in text
    assert "[REDACTED:private_key]" in text


def test_write_compact_trace_preserves_normal_content(tmp_path):
    """Event content with no secrets is written through unchanged as valid JSONL."""
    trace = _trace_with_content("let's ship the release notes tomorrow")
    destination = tmp_path / "trace.jsonl"

    write_compact_trace(trace, destination)

    lines = destination.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    parsed = json.loads(lines[0])
    assert parsed["message"]["content"] == "let's ship the release notes tomorrow"


def test_write_compact_trace_output_stays_valid_jsonl_after_redaction(tmp_path):
    """Redaction placeholders keep each line valid, parseable JSON."""
    trace = _trace_with_content(
        "contact jane@example.com or use sk-abcdefghijklmnop0000"
    )
    destination = tmp_path / "trace.jsonl"

    write_compact_trace(trace, destination)

    lines = [
        line for line in destination.read_text(encoding="utf-8").splitlines() if line
    ]
    assert len(lines) == 1
    parsed = json.loads(lines[0])
    assert "[REDACTED:email]" in parsed["message"]["content"]
    assert "[REDACTED:api_key]" in parsed["message"]["content"]
