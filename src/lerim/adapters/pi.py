"""pi session adapter for completed JSONL sessions.

pi stores sessions as JSON Lines under ``~/.pi/agent/sessions``. The format is
documented by pi as a tree of session entries with ``message``, ``compaction``,
``branch_summary``, and related metadata records. This adapter keeps only the
conversation/context entries that can feed Lerim's compiler, clears bulky tool
outputs and thinking blocks, and writes canonical Lerim JSONL cache files.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from lerim.adapters.base import SessionRecord
from lerim.adapters.common import (
    compact_jsonl,
    compute_file_hash,
    count_non_empty_files,
    in_window,
    load_jsonl_dict_lines,
    make_canonical_entry,
    normalize_timestamp_iso,
    parse_timestamp,
    write_session_cache,
)
from lerim.config.settings import get_trace_cache_dir


_MESSAGE_ROLES = frozenset({"user", "assistant"})


def default_path() -> Path | None:
    """Return the default pi session directory."""
    return Path("~/.pi/agent/sessions/").expanduser()


def _default_cache_dir() -> Path:
    """Return the default cache directory for compacted pi traces."""
    return get_trace_cache_dir("pi")


def count_sessions(path: Path) -> int:
    """Count readable non-empty pi session JSONL files."""
    return count_non_empty_files(path, "*.jsonl")


def validate_connection(path: Path) -> dict[str, Any]:
    """Check whether *path* looks like a pi session directory."""
    if not path.exists():
        return {"ok": False, "error": f"Path does not exist: {path}"}
    sessions = count_sessions(path)
    return {"ok": True, "sessions": sessions}


def compact_trace(raw_text: str) -> str:
    """Convert pi JSONL entries into Lerim's compact canonical trace schema."""
    return compact_jsonl(raw_text, _clean_entry)


def _clean_entry(obj: dict[str, Any]) -> dict[str, Any] | None:
    """Return a compact canonical entry for one pi session row."""
    entry_type = str(obj.get("type") or "")
    timestamp = normalize_timestamp_iso(obj.get("timestamp"))

    if entry_type == "message":
        message = obj.get("message")
        if not isinstance(message, dict):
            return None
        role = str(message.get("role") or "")
        return _clean_message(role=role, message=message, timestamp=timestamp)

    if entry_type == "custom_message":
        content = _clean_content(obj.get("content"))
        if not content:
            return None
        return make_canonical_entry("assistant", "assistant", content, timestamp)

    if entry_type == "compaction":
        summary = str(obj.get("summary") or "").strip()
        if not summary:
            return None
        return make_canonical_entry(
            "assistant",
            "assistant",
            f"[compaction summary]\n{summary}",
            timestamp,
        )

    if entry_type == "branch_summary":
        summary = str(obj.get("summary") or "").strip()
        if not summary:
            return None
        return make_canonical_entry(
            "assistant",
            "assistant",
            f"[branch summary]\n{summary}",
            timestamp,
        )

    return None


def _clean_message(
    *,
    role: str,
    message: dict[str, Any],
    timestamp: str | None,
) -> dict[str, Any] | None:
    """Normalize a pi message object into a canonical entry."""
    if role in _MESSAGE_ROLES:
        content = _clean_content(message.get("content"))
        if not content:
            return None
        return make_canonical_entry(role, role, content, timestamp)

    if role == "toolResult":
        name = str(message.get("toolName") or "tool")
        content = _cleared_tool_content(message.get("content"))
        block: dict[str, Any] = {
            "type": "tool_result",
            "name": name,
            "content": content,
        }
        if message.get("isError") is not None:
            block["is_error"] = bool(message.get("isError"))
        return make_canonical_entry("assistant", "assistant", [block], timestamp)

    if role == "bashExecution":
        if message.get("excludeFromContext") is True:
            return None
        command = str(message.get("command") or "")
        output = _cleared_tool_content(message.get("output"))
        block = {
            "type": "tool_result",
            "name": "bash",
            "input": command,
            "content": output,
        }
        exit_code = message.get("exitCode")
        if exit_code is not None:
            block["exit_code"] = exit_code
        return make_canonical_entry("assistant", "assistant", [block], timestamp)

    if role in {"custom", "branchSummary", "compactionSummary"}:
        content = _summary_message_content(role, message)
        if not content:
            return None
        return make_canonical_entry("assistant", "assistant", content, timestamp)

    return None


def _summary_message_content(role: str, message: dict[str, Any]) -> str:
    """Return text for summary-like pi AgentMessage variants."""
    if role == "custom":
        return _content_to_text(message.get("content"))
    summary = str(message.get("summary") or "").strip()
    if not summary:
        return ""
    label = "branch summary" if role == "branchSummary" else "compaction summary"
    return f"[{label}]\n{summary}"


def _clean_content(content: Any) -> str | list[dict[str, Any]]:
    """Clean a pi message content value while preserving useful text/tool shape."""
    if isinstance(content, str):
        return content.strip()
    if not isinstance(content, list):
        return ""

    cleaned: list[dict[str, Any]] = []
    for block in content:
        if not isinstance(block, dict):
            continue
        block_type = str(block.get("type") or "")
        if block_type == "text":
            text = str(block.get("text") or "").strip()
            if text:
                cleaned.append({"type": "text", "text": text})
        elif block_type == "toolCall":
            cleaned.append(
                {
                    "type": "tool_use",
                    "name": str(block.get("name") or "tool"),
                    "input": block.get("arguments") or block.get("input") or {},
                }
            )
        elif block_type == "toolResult":
            cleaned.append(
                {
                    "type": "tool_result",
                    "name": str(block.get("name") or "tool"),
                    "content": _cleared_tool_content(block.get("content")),
                }
            )
        elif block_type == "thinking":
            thinking = str(block.get("thinking") or "")
            cleaned.append(
                {
                    "type": "thinking",
                    "thinking": f"[thinking cleared: {len(thinking)} chars]",
                }
            )
        elif block_type == "image":
            cleaned.append(
                {
                    "type": "image",
                    "content": "[image cleared]",
                    "mimeType": block.get("mimeType") or block.get("mime_type"),
                }
            )
    return cleaned


def _cleared_tool_content(value: Any) -> str:
    """Return a deterministic descriptor for tool output content."""
    if isinstance(value, str):
        if value.startswith("[cleared:"):
            return value
        return f"[cleared: {len(value)} chars]"
    if isinstance(value, list):
        total = 0
        for item in value:
            if isinstance(item, dict):
                total += len(str(item.get("text") or item.get("content") or ""))
            else:
                total += len(str(item))
        return f"[cleared: {total} chars]"
    if value is None:
        return "[cleared: 0 chars]"
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return f"[cleared: {len(raw)} chars]"


def _content_to_text(content: Any) -> str:
    """Extract user-visible text from pi string or content blocks."""
    cleaned = _clean_content(content)
    if isinstance(cleaned, str):
        return cleaned
    parts: list[str] = []
    for block in cleaned:
        if block.get("type") == "text":
            text = str(block.get("text") or "").strip()
            if text:
                parts.append(text)
    return "\n".join(parts).strip()


def _metadata(entries: list[dict[str, Any]]) -> dict[str, Any]:
    """Collect stable metadata from pi session entries."""
    metadata: dict[str, Any] = {
        "session_id": "",
        "cwd": None,
        "start_time": None,
        "name": None,
        "message_count": 0,
        "tool_calls": 0,
        "errors": 0,
        "total_tokens": 0,
        "summaries": [],
    }
    first_ts: datetime | None = None
    summaries: list[str] = []

    for entry in entries:
        ts = parse_timestamp(entry.get("timestamp"))
        if ts and (first_ts is None or ts < first_ts):
            first_ts = ts

        entry_type = str(entry.get("type") or "")
        if entry_type == "session":
            metadata["session_id"] = str(entry.get("id") or "")
            metadata["cwd"] = entry.get("cwd") or metadata["cwd"]
            continue

        if entry_type == "session_info":
            name = str(entry.get("name") or "").strip()
            if name:
                metadata["name"] = name
            continue

        if entry_type in {"compaction", "branch_summary"}:
            summary = str(entry.get("summary") or "").strip()
            if summary and len(summaries) < 5:
                summaries.append(summary[:140])
            continue

        if entry_type == "message":
            message = entry.get("message")
            if isinstance(message, dict):
                _update_message_metadata(metadata, message, summaries)
            continue

        if entry_type == "custom_message":
            metadata["message_count"] += 1
            text = _content_to_text(entry.get("content"))
            if text and len(summaries) < 5:
                summaries.append(text[:140])

    metadata["start_time"] = first_ts
    metadata["summaries"] = summaries
    return metadata


def _update_message_metadata(
    metadata: dict[str, Any],
    message: dict[str, Any],
    summaries: list[str],
) -> None:
    """Update metadata counters from one pi AgentMessage."""
    role = str(message.get("role") or "")
    if role in {"user", "assistant", "custom"}:
        metadata["message_count"] += 1
        text = _content_to_text(message.get("content"))
        if text and len(summaries) < 5:
            summaries.append(text[:140])

    if role == "toolResult":
        metadata["tool_calls"] += 1
        if message.get("isError") is True:
            metadata["errors"] += 1
    if role == "bashExecution":
        metadata["tool_calls"] += 1
        exit_code = message.get("exitCode")
        if isinstance(exit_code, int) and exit_code != 0:
            metadata["errors"] += 1

    usage = message.get("usage")
    if isinstance(usage, dict):
        metadata["total_tokens"] += _usage_tokens(usage)

    content = message.get("content")
    if isinstance(content, list):
        for block in content:
            if not isinstance(block, dict):
                continue
            block_type = str(block.get("type") or "")
            if block_type == "toolCall":
                metadata["tool_calls"] += 1
            elif block_type == "toolResult":
                metadata["tool_calls"] += 1
                if block.get("isError") is True:
                    metadata["errors"] += 1


def _usage_tokens(usage: dict[str, Any]) -> int:
    """Return a best-effort total token count from pi usage metadata."""
    total = usage.get("totalTokens") or usage.get("total_tokens")
    if isinstance(total, int):
        return total
    count = 0
    for key in (
        "inputTokens",
        "outputTokens",
        "cacheReadTokens",
        "cacheWriteTokens",
        "input_tokens",
        "output_tokens",
        "cache_read_tokens",
        "cache_write_tokens",
    ):
        value = usage.get(key)
        if isinstance(value, int):
            count += value
    return count


def iter_sessions(
    traces_dir: Path | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    known_run_ids: set[str] | None = None,
) -> list[SessionRecord]:
    """Enumerate pi sessions and optionally skip already indexed IDs."""
    base = traces_dir or default_path()
    if base is None or not base.exists():
        return []

    cache_dir = _default_cache_dir()
    records: list[SessionRecord] = []
    for path in base.rglob("*.jsonl"):
        entries = load_jsonl_dict_lines(path)
        if not entries:
            continue
        info = _metadata(entries)
        run_id = str(info.get("session_id") or path.stem)
        if known_run_ids and run_id in known_run_ids:
            continue
        start_dt = info.get("start_time")
        if not isinstance(start_dt, datetime):
            start_dt = None
        if not in_window(start_dt, start, end):
            continue

        raw_lines = path.read_text(encoding="utf-8", errors="replace").rstrip("\n").split("\n")
        cache_path = write_session_cache(cache_dir, run_id, raw_lines, compact_trace)
        content_hash = compute_file_hash(cache_path)

        repo_path = str(info.get("cwd") or "") or None
        repo_name = Path(repo_path).name if repo_path else str(info.get("name") or "") or None

        records.append(
            SessionRecord(
                run_id=run_id,
                agent_type="pi",
                session_path=str(cache_path),
                start_time=start_dt.isoformat() if start_dt else None,
                repo_path=repo_path,
                repo_name=repo_name,
                message_count=int(info.get("message_count") or 0),
                tool_call_count=int(info.get("tool_calls") or 0),
                error_count=int(info.get("errors") or 0),
                total_tokens=int(info.get("total_tokens") or 0),
                summaries=list(info.get("summaries") or [])[:5],
                content_hash=content_hash,
            )
        )

    records.sort(key=lambda record: (record.start_time or "", record.run_id))
    return records
