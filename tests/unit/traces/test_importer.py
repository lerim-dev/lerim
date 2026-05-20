"""Tests for host-only generic trace imports."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from lerim.context import ContextStore, resolve_scope_identity
from lerim.traces.envelope import load_generic_trace, write_compact_trace
from lerim.traces.importer import _normalized_trace_path, import_trace_file
from tests.helpers import make_config


class _FakeRuntime:
    """Runtime double that captures imported ingest calls."""

    calls: list[dict[str, Any]] = []

    def __init__(self, *, config) -> None:
        self.config = config

    def ingest_imported_trace(self, trace_path: Path, **kwargs: Any) -> dict[str, Any]:
        """Capture the imported trace extraction call."""
        self.calls.append({"trace_path": trace_path, **kwargs})
        return {
            "trace_path": str(trace_path),
            "context_db_path": str(self.config.context_db_path),
            "project_id": None,
            "scope_type": kwargs["scope_identity"].scope_type,
            "scope_id": kwargs["scope_identity"].scope_id,
            "scope_label": kwargs["scope_identity"].label,
            "workspace_root": str(self.config.global_data_dir / "workspace"),
            "run_folder": str(self.config.global_data_dir / "workspace" / "ingest-run"),
            "artifacts": {},
            "records_created": 1,
            "records_updated": 0,
            "records_archived": 0,
            "cost_usd": 0.0,
        }


def test_import_trace_file_normalizes_and_calls_runtime(tmp_path, monkeypatch):
    """Importer writes a compact trace and extracts it through scoped runtime."""
    _FakeRuntime.calls = []
    monkeypatch.setattr("lerim.traces.importer.LerimRuntime", _FakeRuntime)
    trace_path = tmp_path / "raw.jsonl"
    trace_path.write_text('{"role":"user","content":"hello"}\n', encoding="utf-8")
    cfg = make_config(tmp_path / ".lerim")

    result = import_trace_file(
        trace_path=trace_path,
        source_name="support-bot",
        source_profile="support",
        scope_type="domain",
        scope="support",
        config=cfg,
    )

    assert result.normalized_trace_path.is_file()
    assert result.scope_identity.scope_type == "domain"
    assert result.ingest_result["records_created"] == 1
    assert _FakeRuntime.calls[0]["source_name"] == "support-bot"
    assert _FakeRuntime.calls[0]["session_meta"]["content_hash"]


def test_import_trace_file_uses_wrapper_session_id(tmp_path, monkeypatch):
    """Importer prefers a wrapper session id when CLI/MCP did not pass one."""
    _FakeRuntime.calls = []
    monkeypatch.setattr("lerim.traces.importer.LerimRuntime", _FakeRuntime)
    trace_path = tmp_path / "raw.json"
    trace_path.write_text(
        '{"session_id":"sess-wrapper","messages":[{"role":"user","content":"hello"}]}',
        encoding="utf-8",
    )
    cfg = make_config(tmp_path / ".lerim")

    result = import_trace_file(
        trace_path=trace_path,
        source_name="support-bot",
        source_profile="support",
        scope_type="domain",
        scope="support",
        config=cfg,
    )

    assert result.session_id == "sess-wrapper"
    assert _FakeRuntime.calls[0]["session_id"] == "sess-wrapper"


def test_import_trace_file_skips_exact_duplicate_session(
    tmp_path,
    monkeypatch,
):
    """Importer skips extraction when session id and normalized content match."""
    _FakeRuntime.calls = []
    monkeypatch.setattr("lerim.traces.importer.LerimRuntime", _FakeRuntime)
    trace_path = tmp_path / "raw.jsonl"
    trace_path.write_text('{"role":"user","content":"hello"}\n', encoding="utf-8")
    cfg = make_config(tmp_path / ".lerim")
    scope = resolve_scope_identity(scope_type="domain", scope="support")
    normalized = load_generic_trace(trace_path)
    normalized_path = _normalized_trace_path(
        cfg,
        scope_identity=scope,
        trace_id=normalized.trace_id,
    )
    write_compact_trace(normalized, normalized_path)
    ContextStore(cfg.context_db_path).upsert_session(
        project_id=None,
        session_id="sess-dup",
        agent_type="support-bot",
        source_trace_ref=str(normalized_path),
        repo_path=None,
        cwd=None,
        started_at=None,
        model_name="test-model",
        instructions_text=None,
        prompt_text=None,
        scope_identity=scope,
        source_name="support-bot",
        source_profile="support",
    )

    result = import_trace_file(
        trace_path=trace_path,
        source_name="support-bot",
        source_profile="support",
        scope_type="domain",
        scope="support",
        session_id="sess-dup",
        config=cfg,
    )

    assert result.ingest_result["status"] == "duplicate_skipped"
    assert result.ingest_result["records_created"] == 0
    assert _FakeRuntime.calls == []


def test_import_trace_file_force_reruns_exact_duplicate(
    tmp_path,
    monkeypatch,
):
    """Importer force mode reruns extraction even for exact duplicate content."""
    _FakeRuntime.calls = []
    monkeypatch.setattr("lerim.traces.importer.LerimRuntime", _FakeRuntime)
    trace_path = tmp_path / "raw.jsonl"
    trace_path.write_text('{"role":"user","content":"hello"}\n', encoding="utf-8")
    cfg = make_config(tmp_path / ".lerim")
    scope = resolve_scope_identity(scope_type="domain", scope="support")
    normalized = load_generic_trace(trace_path)
    normalized_path = _normalized_trace_path(
        cfg,
        scope_identity=scope,
        trace_id=normalized.trace_id,
    )
    write_compact_trace(normalized, normalized_path)
    ContextStore(cfg.context_db_path).upsert_session(
        project_id=None,
        session_id="sess-dup",
        agent_type="support-bot",
        source_trace_ref=str(normalized_path),
        repo_path=None,
        cwd=None,
        started_at=None,
        model_name="test-model",
        instructions_text=None,
        prompt_text=None,
        scope_identity=scope,
        source_name="support-bot",
        source_profile="support",
    )

    result = import_trace_file(
        trace_path=trace_path,
        source_name="support-bot",
        source_profile="support",
        scope_type="domain",
        scope="support",
        session_id="sess-dup",
        force=True,
        config=cfg,
    )

    assert result.ingest_result["records_created"] == 1
    assert _FakeRuntime.calls
