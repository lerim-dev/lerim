"""Host-only generic trace import orchestration."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from lerim.config.settings import Config, get_config
from lerim.context import ContextStore, ScopeIdentity, resolve_scope_identity
from lerim.server.runtime import LerimRuntime
from lerim.traces.envelope import load_generic_trace, write_compact_trace


@dataclass(frozen=True)
class TraceImportResult:
    """Result returned after importing and ingesting a generic trace."""

    trace_id: str
    normalized_trace_path: Path
    scope_identity: ScopeIdentity
    session_id: str
    ingest_result: dict[str, Any]


def import_trace_file(
    *,
    trace_path: Path,
    source_name: str,
    source_profile: str,
    scope_type: str,
    scope: str,
    scope_label: str | None = None,
    session_id: str | None = None,
    force: bool = False,
    config: Config | None = None,
) -> TraceImportResult:
    """Normalize, register, and extract one explicit generic trace file."""
    cfg = config or get_config()
    resolved_trace = trace_path.expanduser().resolve()
    normalized = load_generic_trace(resolved_trace)
    scope_identity = resolve_scope_identity(
        scope_type=scope_type,
        scope=scope,
        scope_label=scope_label,
    )
    normalized_path = _normalized_trace_path(
        cfg,
        scope_identity=scope_identity,
        trace_id=normalized.trace_id,
    )
    write_compact_trace(normalized, normalized_path)
    resolved_session_id = session_id or normalized.session_id or normalized.trace_id
    if not force and _is_duplicate_import(
        config=cfg,
        session_id=resolved_session_id,
        normalized_trace_path=normalized_path,
    ):
        return TraceImportResult(
            trace_id=normalized.trace_id,
            normalized_trace_path=normalized_path,
            scope_identity=scope_identity,
            session_id=resolved_session_id,
            ingest_result={
                "status": "duplicate_skipped",
                "trace_path": str(normalized_path),
                "context_db_path": str(cfg.context_db_path),
                "project_id": (
                    scope_identity.scope_id
                    if scope_identity.scope_type == "project"
                    else None
                ),
                "scope_type": scope_identity.scope_type,
                "scope_id": scope_identity.scope_id,
                "scope_label": scope_identity.label,
                "workspace_root": str(cfg.global_data_dir / "workspace"),
                "run_folder": "",
                "artifacts": {},
                "records_created": 0,
                "records_updated": 0,
                "records_archived": 0,
                "cost_usd": 0.0,
            },
        )
    runtime = LerimRuntime(config=cfg)
    ingest_result = runtime.ingest_imported_trace(
        normalized_path,
        scope_identity=scope_identity,
        session_id=resolved_session_id,
        agent_type=source_name or "generic",
        source_name=source_name,
        source_profile=source_profile,
        session_meta={
            "started_at": normalized.started_at or "",
            "source_trace_path": str(resolved_trace),
            "message_count": normalized.message_count,
            "content_hash": normalized.content_hash,
            "trace_metadata": normalized.metadata or {},
        },
    )
    return TraceImportResult(
        trace_id=normalized.trace_id,
        normalized_trace_path=normalized_path,
        scope_identity=scope_identity,
        session_id=resolved_session_id,
        ingest_result=ingest_result,
    )


def _normalized_trace_path(
    config: Config,
    *,
    scope_identity: ScopeIdentity,
    trace_id: str,
) -> Path:
    """Return the canonical workspace path for normalized imports."""
    return (
        config.global_data_dir
        / "workspace"
        / "imports"
        / scope_identity.scope_type
        / scope_identity.scope_id
        / f"{trace_id}.jsonl"
    )


def _is_duplicate_import(
    *,
    config: Config,
    session_id: str,
    normalized_trace_path: Path,
) -> bool:
    """Return whether the same session already points at identical trace content."""
    store = ContextStore(config.context_db_path)
    store.initialize()
    with store.connect() as conn:
        row = conn.execute(
            "SELECT source_trace_ref FROM sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()
    if row is None:
        return False
    previous_path = Path(str(row["source_trace_ref"] or "")).expanduser()
    if not previous_path.is_file() or not normalized_trace_path.is_file():
        return False
    return _file_sha256(previous_path) == _file_sha256(normalized_trace_path)


def _file_sha256(path: Path) -> str:
    """Return the SHA-256 hash for one local file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    """Run a tiny path construction smoke check."""
    from tempfile import TemporaryDirectory

    from lerim.config.settings import Config

    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        cfg = Config(global_data_dir=root, server_port=3030)
        scope = resolve_scope_identity(scope_type="domain", scope="support")
        path = _normalized_trace_path(cfg, scope_identity=scope, trace_id="trace_demo")
        assert "imports" in path.parts
