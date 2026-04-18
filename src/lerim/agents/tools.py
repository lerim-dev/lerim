"""Agent tools for Lerim's DB-only context architecture.

This module defines the agent-facing tool surface for extract, maintain, and
ask. Durable context operations are semantic and DB-backed:

- `trace_read`
- `context_search`
- `context_fetch`
- `context_apply`

The extract flow also keeps two local reasoning tools:

- `note`
- `prune`
"""

from __future__ import annotations

from dataclasses import replace
import json
import math
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from pydantic_ai import RunContext
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    SystemPromptPart,
    ToolCallPart,
    ToolReturnPart,
)

from lerim.context import ContextStore, ProjectIdentity

TRACE_MAX_LINES_PER_READ = 100
TRACE_MAX_LINE_BYTES = 5_000
TRACE_MAX_CHUNK_BYTES = 50_000
MODEL_CONTEXT_TOKEN_LIMIT = 128_000
CONTEXT_SOFT_PRESSURE_PCT = 0.60
CONTEXT_HARD_PRESSURE_PCT = 0.80
_TOKENS_PER_CHAR = 0.25
PRUNED_STUB = "[pruned]"
_DEFAULT_DOMAIN_ALIASES = {"", "default"}


class Finding(BaseModel):
    """Structured extract finding captured during trace scanning."""

    theme: str = Field(description="Short theme label for the finding.")
    offset: int = Field(description="Trace line where the supporting evidence appears.")
    quote: str = Field(description="Short verbatim evidence snippet from the trace.")
    level: str = Field(
        description=(
            "Signal level: decision, preference, feedback, reference, "
            "constraint, fact, or implementation."
        )
    )


@dataclass
class ContextDeps:
    """Dependencies and per-run state shared across tool calls."""

    context_db_path: Path
    project_identity: ProjectIdentity
    session_id: str
    project_ids: list[str] | None = None
    trace_path: Path | None = None
    run_folder: Path | None = None
    notes: list[Finding] = field(default_factory=list)
    pruned_offsets: set[int] = field(default_factory=set)


def _store(ctx: RunContext[ContextDeps]) -> ContextStore:
    """Return the canonical context store for the current run."""
    store = ContextStore(ctx.deps.context_db_path)
    store.initialize()
    store.register_project(ctx.deps.project_identity)
    return store


def _trace_lines(trace_path: Path) -> list[str]:
    """Read the current trace file into a list of lines."""
    return trace_path.read_text(encoding="utf-8").splitlines()


def _normalize_domain(value: Any) -> str:
    """Normalize agent-facing domain values to canonical store enums."""
    domain = str(value or "").strip().lower()
    if domain in _DEFAULT_DOMAIN_ALIASES:
        return "project"
    return domain


def trace_read(ctx: RunContext[ContextDeps], offset: int = 0, limit: int = 100) -> str:
    """Read normalized trace chunks with line numbers and bounded size."""
    trace_path = ctx.deps.trace_path
    if trace_path is None:
        return "Error: no trace path configured"
    if limit <= 0 or limit > TRACE_MAX_LINES_PER_READ:
        limit = TRACE_MAX_LINES_PER_READ
    lines = _trace_lines(trace_path)
    total = len(lines)
    chunk = lines[offset : offset + limit]
    safe_chunk: list[str] = []
    running_bytes = 0
    for line in chunk:
        if len(line) > TRACE_MAX_LINE_BYTES:
            dropped = len(line) - TRACE_MAX_LINE_BYTES
            line = line[:TRACE_MAX_LINE_BYTES] + f" ... [truncated {dropped} chars from this line]"
        line_bytes = len(line.encode("utf-8"))
        if running_bytes + line_bytes > TRACE_MAX_CHUNK_BYTES:
            break
        safe_chunk.append(line)
        running_bytes += line_bytes
    numbered = [f"{offset + index + 1}\t{line}" for index, line in enumerate(safe_chunk)]
    last_line = offset + len(safe_chunk)
    header = f"[{total} lines, showing {offset + 1}-{last_line}]"
    if last_line < total:
        header += (
            f" — {total - last_line} more lines, call "
            f"trace_read(offset={last_line}, limit={TRACE_MAX_LINES_PER_READ}) for the next chunk"
        )
    return header + "\n" + "\n".join(numbered)


def context_search(
    ctx: RunContext[ContextDeps],
    query: str,
    kind_filters: list[str] | None = None,
    domain_filters: list[str] | None = None,
    as_of: str = "",
    include_history: bool = False,
    limit: int = 8,
) -> str:
    """Search the context store with hybrid retrieval and compact results."""
    if not str(query or "").strip():
        return json.dumps({"count": 0, "hits": []}, indent=2)
    store = _store(ctx)
    hits = store.search(
        project_ids=ctx.deps.project_ids or [ctx.deps.project_identity.project_id],
        query=query,
        kind_filters=kind_filters or None,
        domain_filters=domain_filters or None,
        as_of=as_of.strip() or None,
        include_history=bool(include_history),
        limit=max(1, min(int(limit), 8)),
    )
    payload = {
        "count": len(hits),
        "hits": [
            {
                "record_id": hit.record_id,
                "kind": hit.kind,
                "domain": hit.domain,
                "title": hit.title,
                "summary": hit.summary,
                "status": hit.status,
                "score": round(hit.score, 6),
                "sources": hit.sources,
            }
            for hit in hits
        ],
    }
    return json.dumps(payload, ensure_ascii=True, indent=2)


def context_fetch(
    ctx: RunContext[ContextDeps],
    record_ids: list[str],
    include_versions: bool = False,
    include_evidence: bool = False,
    include_links: bool = False,
    response_format: str = "concise",
) -> str:
    """Fetch canonical records by ID with concise or detailed response formats."""
    mode = (response_format or "concise").strip().lower()
    if mode not in {"concise", "detailed"}:
        return f"Error: response_format must be 'concise' or 'detailed', got {response_format!r}"
    if not record_ids:
        return json.dumps({"count": 0, "records": []}, indent=2)
    store = _store(ctx)
    allowed_project_ids = ctx.deps.project_ids or [ctx.deps.project_identity.project_id]
    records: list[dict[str, Any]] = []
    for record_id in record_ids:
        record = store.fetch_record(
            record_id,
            project_ids=allowed_project_ids,
            include_versions=bool(include_versions),
            include_evidence=bool(include_evidence),
            include_links=bool(include_links),
        )
        if record is None:
            continue
        if mode == "concise":
            records.append(
                {
                    "record_id": record["record_id"],
                    "kind": record["kind"],
                    "domain": record["domain"],
                    "title": record["title"],
                    "summary": record["summary"],
                    "content_md": record["content_md"][:2000],
                    "status": record["status"],
                }
            )
            continue
        records.append(record)
    return json.dumps({"count": len(records), "records": records}, ensure_ascii=True, indent=2)


def context_apply(ctx: RunContext[ContextDeps], op: str, payload: dict[str, Any]) -> str:
    """Apply one semantic mutation to the context store."""
    operation = (op or "").strip()
    if not operation:
        return "Error: op is required"
    if not isinstance(payload, dict):
        return "Error: payload must be an object"
    store = _store(ctx)
    project_id = ctx.deps.project_identity.project_id
    session_id = ctx.deps.session_id
    try:
        if operation == "create_record":
            result = store.create_record(
                project_id=project_id,
                session_id=session_id,
                kind=str(payload.get("kind") or "").strip(),
                domain=_normalize_domain(payload.get("domain")),
                title=str(payload.get("title") or "").strip(),
                summary=str(payload.get("summary") or "").strip(),
                structured=dict(payload.get("structured") or {}),
                status=str(payload.get("status") or "active").strip(),
                confidence=payload.get("confidence"),
                valid_from=str(payload.get("valid_from") or "").strip() or None,
                valid_until=payload.get("valid_until"),
                links=list(payload.get("links") or []),
                evidence=list(payload.get("evidence") or []),
                change_reason=str(payload.get("change_reason") or "").strip() or None,
            )
        elif operation == "update_record":
            result = store.update_record(
                record_id=str(payload.get("record_id") or "").strip(),
                session_id=session_id,
                changes={
                    **dict(payload.get("changes") or {}),
                    **(
                        {"domain": _normalize_domain(dict(payload.get("changes") or {}).get("domain"))}
                        if "domain" in dict(payload.get("changes") or {})
                        else {}
                    ),
                },
                change_reason=str(payload.get("change_reason") or "").strip() or None,
            )
        elif operation == "archive_record":
            result = store.archive_record(
                record_id=str(payload.get("record_id") or "").strip(),
                session_id=session_id,
                reason=str(payload.get("reason") or "").strip() or None,
            )
        elif operation == "supersede_record":
            result = store.supersede_record(
                record_id=str(payload.get("record_id") or "").strip(),
                session_id=session_id,
                replacement_record_id=str(payload.get("replacement_record_id") or "").strip(),
                reason=str(payload.get("reason") or "").strip() or None,
                valid_until=str(payload.get("valid_until") or "").strip() or None,
            )
        elif operation == "link_records":
            result = store.link_records(
                project_id=project_id,
                from_record_id=str(payload.get("from_record_id") or "").strip(),
                to_record_id=str(payload.get("to_record_id") or "").strip(),
                relation=str(payload.get("relation") or "").strip(),
                reason=str(payload.get("reason") or "").strip() or None,
                session_id=session_id,
            )
        else:
            return (
                "Error: op must be one of "
                "'create_record', 'update_record', 'archive_record', "
                "'supersede_record', or 'link_records'"
            )
    except Exception as exc:
        return f"Error: {exc}"
    return json.dumps({"ok": True, "op": operation, "result": result}, ensure_ascii=True, indent=2)


def note(ctx: RunContext[ContextDeps], findings: list[Finding]) -> str:
    """Record structured findings from the trace chunks just read."""
    if not findings:
        return "No findings recorded."
    ctx.deps.notes.extend(findings)
    store = _store(ctx)
    store.add_session_findings(
        project_id=ctx.deps.project_identity.project_id,
        session_id=ctx.deps.session_id,
        findings=[finding.model_dump(mode="json") for finding in findings],
    )
    total = len(ctx.deps.notes)
    return f"Noted {len(findings)} findings (total {total} so far)."


def prune(ctx: RunContext[ContextDeps], trace_offsets: list[int]) -> str:
    """Stub prior trace reads in future turns to reduce context pressure."""
    if not trace_offsets:
        return "No offsets to prune."
    before = len(ctx.deps.pruned_offsets)
    ctx.deps.pruned_offsets.update(int(offset) for offset in trace_offsets)
    added = len(ctx.deps.pruned_offsets) - before
    return f"Pruned {added} new offset(s); total pruned: {len(ctx.deps.pruned_offsets)}."


def compute_request_budget(trace_path: Path) -> int:
    """Scale extract request budget from trace size.

    Real traces need more headroom than the old 20-turn floor allowed,
    even when the trace itself is short. Keep the budget adaptive, but
    bias toward successful completion over premature request-limit exits.
    """
    try:
        line_count = sum(1 for _ in trace_path.open("r", encoding="utf-8"))
    except OSError:
        return 40
    if line_count <= 200:
        return 40
    if line_count >= 5000:
        return 100
    return max(40, min(100, int(40 + (line_count / 100.0))))


def notes_state_injector(
    ctx: RunContext[ContextDeps],
    history: list[ModelMessage],
) -> list[ModelMessage]:
    """Inject a compact notes dashboard into the next model request."""
    findings = ctx.deps.notes
    if not findings:
        summary = "NOTES: 0 findings"
    else:
        counts = Counter(f.level for f in findings)
        themes = Counter(f.theme for f in findings)
        durable = sum(counts.get(level, 0) for level in ("decision", "preference", "feedback", "reference", "constraint", "fact"))
        implementation = counts.get("implementation", 0)
        top_themes = ", ".join(f"{theme}({count})" for theme, count in themes.most_common(5))
        summary = (
            f"NOTES: {len(findings)} findings ({durable} durable, {implementation} implementation) "
            f"across {len(themes)} theme(s)"
        )
        if top_themes:
            summary += f"\nTop themes: {top_themes}"
    injected = list(history)
    injected.append(ModelRequest(parts=[SystemPromptPart(content=summary)]))
    return injected


def context_pressure_injector(
    ctx: RunContext[ContextDeps],
    history: list[ModelMessage],
) -> list[ModelMessage]:
    """Inject approximate context pressure information into the next model request."""
    del ctx
    chars = 0
    for message in history:
        parts = getattr(message, "parts", []) or []
        for part in parts:
            content = getattr(part, "content", None)
            if isinstance(content, str):
                chars += len(content)
            elif content is not None:
                chars += len(json.dumps(content, ensure_ascii=True))
    approx_tokens = math.ceil(chars * _TOKENS_PER_CHAR)
    pct = approx_tokens / MODEL_CONTEXT_TOKEN_LIMIT
    pressure = "soft" if pct >= CONTEXT_SOFT_PRESSURE_PCT else "normal"
    if pct >= CONTEXT_HARD_PRESSURE_PCT:
        pressure = "hard"
    summary = f"CONTEXT: {approx_tokens}/{MODEL_CONTEXT_TOKEN_LIMIT} ({pct:.0%}) [{pressure}]"
    injected = list(history)
    injected.append(ModelRequest(parts=[SystemPromptPart(content=summary)]))
    return injected


def prune_history_processor(
    ctx: RunContext[ContextDeps],
    history: list[ModelMessage],
) -> list[ModelMessage]:
    """Rewrite prior trace_read results to tiny stubs for pruned offsets."""
    if not ctx.deps.pruned_offsets:
        return history
    pruned = set(ctx.deps.pruned_offsets)
    rewritten: list[ModelMessage] = []
    pending_offset: int | None = None
    for message in history:
        parts = getattr(message, "parts", []) or []
        new_parts = []
        for part in parts:
            if isinstance(part, ToolCallPart) and getattr(part, "tool_name", "") == "trace_read":
                args = getattr(part, "args", None)
                offset = None
                if isinstance(args, dict):
                    try:
                        offset = int(args.get("offset", 0))
                    except Exception:
                        offset = 0
                pending_offset = offset
                new_parts.append(part)
                continue
            if (
                isinstance(part, ToolReturnPart)
                and pending_offset in pruned
                and isinstance(part.content, str)
            ):
                new_parts.append(replace(part, content=PRUNED_STUB))
                pending_offset = None
                continue
            new_parts.append(part)
            if isinstance(part, ToolReturnPart):
                pending_offset = None
        rewritten.append(replace(message, parts=new_parts))
    return rewritten


if __name__ == "__main__":
    """Run a small smoke check for request budget logic."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        trace_path = Path(tmp) / "trace.jsonl"
        trace_path.write_text("\n".join(f"line {i}" for i in range(240)), encoding="utf-8")
        budget = compute_request_budget(trace_path)
        assert budget >= 20
        print("agent tools: self-test passed")
