"""Unit tests for redaction wiring in lerim.adapters.common.write_session_cache.

write_session_cache funnels every built-in adapter's compacted session
output through redact_text before the cache file is written, so these
tests exercise that specific wiring rather than the redaction patterns
themselves (covered in tests/unit/test_redaction.py).
"""

from __future__ import annotations

from lerim.adapters.common import write_session_cache


def test_write_session_cache_redacts_secret_in_compacted_output(tmp_path):
    """A secret present in the compacted text is redacted before writing."""
    cache_dir = tmp_path / "cache"
    lines = ['{"message":"my key is sk-abcdefghijklmnopqrstuvwx1234"}']

    def identity_compact(raw: str) -> str:
        """Identity compactor -- returns input unchanged."""
        return raw

    result_path = write_session_cache(cache_dir, "run-secret", lines, identity_compact)

    content = result_path.read_text(encoding="utf-8")
    assert "sk-abcdefghijklmnopqrstuvwx1234" not in content
    assert "[REDACTED:api_key]" in content


def test_write_session_cache_redacts_email_produced_by_compact_fn(tmp_path):
    """Redaction runs on compact_fn's output, not just the raw input lines."""
    cache_dir = tmp_path / "cache"

    def append_email(raw: str) -> str:
        """Compactor that appends an email address, simulating adapter output."""
        return raw.strip() + " contact ops@example.com\n"

    write_session_cache(cache_dir, "run-email", ["hello"], append_email)
    content = (cache_dir / "run-email.jsonl").read_text(encoding="utf-8")

    assert "ops@example.com" not in content
    assert "[REDACTED:email]" in content


def test_write_session_cache_redacts_bearer_token(tmp_path):
    """A bearer token embedded in session lines is redacted before writing."""
    cache_dir = tmp_path / "cache"
    lines = ['{"header":"Authorization: Bearer abcdef1234567890token"}']

    write_session_cache(cache_dir, "run-bearer", lines, lambda raw: raw)
    content = (cache_dir / "run-bearer.jsonl").read_text(encoding="utf-8")

    assert "abcdef1234567890token" not in content
    assert "[REDACTED:token]" in content


def test_write_session_cache_preserves_normal_text(tmp_path):
    """Ordinary session content with no secrets passes through unchanged."""
    cache_dir = tmp_path / "cache"
    lines = ['{"message":"just a normal note about the sprint plan"}']

    write_session_cache(cache_dir, "run-normal", lines, lambda raw: raw)
    content = (cache_dir / "run-normal.jsonl").read_text(encoding="utf-8")

    assert content == '{"message":"just a normal note about the sprint plan"}\n'


def test_write_session_cache_still_returns_correct_path(tmp_path):
    """Wiring in redaction does not change write_session_cache's return value."""
    cache_dir = tmp_path / "cache"
    result_path = write_session_cache(cache_dir, "run-path", ["line"], lambda raw: raw)
    assert result_path == cache_dir / "run-path.jsonl"
    assert result_path.exists()
