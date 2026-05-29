"""Short-term continuation handoff derived from recent context record versions."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from lerim.config.settings import Config
from lerim.context import ContextStore
from lerim.context_brief import (
    ContextBriefProject,
    age_seconds_since,
    count_changed_records_since,
    count_missing_included_records,
    human_age,
    read_manifest,
)

WORKING_MEMORY_FILENAME = "WORKING_MEMORY.md"
WORKING_MEMORY_MANIFEST_FILENAME = "WORKING_MEMORY.manifest.json"
WORKING_MEMORY_OPERATION = "working-memory"
WORKING_MEMORY_WINDOW_HOURS = 2
WORKING_MEMORY_VERSION_LIMIT = 40
WORKING_MEMORY_RECORD_LIMIT = 14
WORKING_MEMORY_LINE_LIMIT = 130
KIND_PRIORITY = {
    "decision": 0,
    "preference": 1,
    "constraint": 2,
    "fact": 3,
    "episode": 4,
}


@dataclass(frozen=True)
class WorkingMemoryPaths:
    """Stable current Working Memory artifact paths for one project."""

    current_dir: Path
    current_file: Path
    current_manifest: Path


@dataclass(frozen=True)
class WorkingMemoryData:
    """Recent version rows plus the records agents should treat as current."""

    versions: tuple[dict[str, Any], ...]
    changed_records: tuple[dict[str, Any], ...]
    current_records: tuple[dict[str, Any], ...]
    replacements: tuple[tuple[str, dict[str, Any]], ...]


@dataclass(frozen=True)
class WorkingMemoryStatus:
    """Freshness and availability metadata for one project's Working Memory."""

    availability: str
    project: str
    project_id: str
    repo_path: str
    generated_at: str | None
    age_seconds: int | None
    window_hours: int
    window_started_at: str | None
    recent_versions_considered: int
    records_included: int
    records_changed_since_generation: int
    records_missing_since_generation: int
    current_file: str
    current_manifest: str
    latest_run_folder: str | None
    suggested_action: str


def working_memory_paths(config: Config, project_id: str) -> WorkingMemoryPaths:
    """Return stable current Working Memory paths for a project."""
    current_dir = config.global_data_dir / "workspace" / "current" / project_id
    return WorkingMemoryPaths(
        current_dir=current_dir,
        current_file=current_dir / WORKING_MEMORY_FILENAME,
        current_manifest=current_dir / WORKING_MEMORY_MANIFEST_FILENAME,
    )


def working_memory_window_start(
    *,
    now: datetime | None = None,
    window_hours: int = WORKING_MEMORY_WINDOW_HOURS,
) -> str:
    """Return the lower timestamp bound for the recent Working Memory window."""
    effective_now = now or datetime.now(timezone.utc)
    if effective_now.tzinfo is None:
        effective_now = effective_now.replace(tzinfo=timezone.utc)
    start = effective_now.astimezone(timezone.utc) - timedelta(hours=max(1, int(window_hours)))
    return start.isoformat()


def load_recent_record_versions(
    store: ContextStore,
    *,
    project_id: str,
    since: str,
    limit: int = WORKING_MEMORY_VERSION_LIMIT,
) -> list[dict[str, Any]]:
    """Load recent record-version rows for one project."""
    payload = store.query(
        entity="versions",
        mode="list",
        project_ids=[project_id],
        updated_since=since,
        order_by="updated_at",
        limit=max(1, int(limit)),
        include_total=False,
    )
    return list(payload.get("rows") or [])


def load_working_memory_data(
    store: ContextStore,
    *,
    project_id: str,
    since: str,
    limit: int = WORKING_MEMORY_VERSION_LIMIT,
) -> WorkingMemoryData:
    """Load recent version rows and resolve their current records."""
    versions = load_recent_record_versions(
        store,
        project_id=project_id,
        since=since,
        limit=limit,
    )
    changed_by_id: dict[str, dict[str, Any]] = {}
    current_by_id: dict[str, dict[str, Any]] = {}
    replacement_by_old_id: dict[str, dict[str, Any]] = {}
    for version in versions:
        record_id = str(version.get("record_id") or "").strip()
        if not record_id:
            continue
        record = store.fetch_record(
            record_id,
            project_ids=[project_id],
            include_versions=False,
        )
        if record is None:
            continue
        changed_by_id.setdefault(record_id, record)
        if is_current_record(record):
            current_by_id.setdefault(record_id, record)
        replacement_id = str(record.get("superseded_by_record_id") or "").strip()
        if replacement_id:
            replacement = store.fetch_record(
                replacement_id,
                project_ids=[project_id],
                include_versions=False,
            )
            if replacement is not None:
                replacement_by_old_id[record_id] = replacement
                if is_current_record(replacement):
                    current_by_id.setdefault(replacement_id, replacement)
    return WorkingMemoryData(
        versions=tuple(versions),
        changed_records=sort_records(changed_by_id.values()),
        current_records=sort_records(current_by_id.values()),
        replacements=tuple(replacement_by_old_id.items()),
    )


def is_current_record(record: dict[str, Any]) -> bool:
    """Return whether a fetched record is the active version agents should use."""
    return (
        str(record.get("status") or "") == "active"
        and not str(record.get("valid_until") or "").strip()
        and not str(record.get("superseded_by_record_id") or "").strip()
    )


def sort_records(records: Any) -> tuple[dict[str, Any], ...]:
    """Return records ordered by durable kind priority and recency."""
    rows = list(records)
    rows.sort(
        key=lambda row: (
            str(row.get("updated_at") or ""),
            str(row.get("record_id") or ""),
        ),
        reverse=True,
    )
    rows.sort(key=lambda row: KIND_PRIORITY.get(str(row.get("kind") or ""), 50))
    return tuple(rows)


def working_memory_record_ids(data: WorkingMemoryData) -> tuple[str, ...]:
    """Return unique record IDs cited by a Working Memory render."""
    ordered: list[str] = []
    seen: set[str] = set()
    for version in data.versions:
        _append_record_id(ordered, seen, version.get("record_id"))
    for record in data.changed_records:
        _append_record_id(ordered, seen, record.get("record_id"))
    for old_record_id, replacement in data.replacements:
        _append_record_id(ordered, seen, old_record_id)
        _append_record_id(ordered, seen, replacement.get("record_id"))
    for record in data.current_records:
        _append_record_id(ordered, seen, record.get("record_id"))
    return tuple(ordered)


def git_output(repo_path: Path, *args: str) -> str | None:
    """Return one git command's stdout for a repo path, or None when unavailable."""
    try:
        result = subprocess.run(
            ("git", "-C", str(repo_path), *args),
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    text = result.stdout.strip()
    return text or None


def summarize_git_status(status: str) -> dict[str, int]:
    """Group porcelain status rows by the changed file's top-level area."""
    groups: dict[str, int] = {}
    for raw_line in status.splitlines():
        path = raw_line[2:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1].strip()
        group = path.split("/", 1)[0] if "/" in path else path
        if not group:
            group = "root"
        groups[group] = groups.get(group, 0) + 1
    return groups


def current_record_status(
    record: dict[str, Any],
    replacement: dict[str, Any] | None,
) -> str:
    """Describe whether a changed record remains current or points elsewhere."""
    if replacement is not None:
        replacement_id = str(replacement.get("record_id") or "")
        replacement_title = compact_text(replacement.get("title"), limit=90)
        return f"use replacement `{replacement_title}` (`{replacement_id}`)"
    if is_current_record(record):
        return "current active record"
    status = str(record.get("status") or "record")
    valid_until = str(record.get("valid_until") or "").strip()
    if valid_until:
        return f"historical after `{valid_until}`"
    return f"historical `{status}` record"


def compact_text(value: Any, *, limit: int) -> str:
    """Return compact single-line text within a character budget."""
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "..."


def truncate_working_memory_lines(lines: list[str]) -> list[str]:
    """Clip Working Memory markdown to a bounded startup size."""
    if len(lines) <= WORKING_MEMORY_LINE_LIMIT:
        return lines
    visible = lines[: max(0, WORKING_MEMORY_LINE_LIMIT - 3)]
    visible.extend(
        [
            "",
            "> Truncated for startup size. Use `lerim query versions list --scope project --json` for deeper detail.",
        ]
    )
    return visible


def build_working_memory_manifest(
    *,
    run_id: str,
    status: str,
    generated_at: str,
    window_started_at: str,
    project: ContextBriefProject,
    data: WorkingMemoryData,
    changed_records_since_previous: int,
    trigger: str,
    current_file: Path,
    run_folder: Path,
) -> dict[str, Any]:
    """Build the Working Memory manifest payload."""
    record_ids = working_memory_record_ids(data)
    return {
        "run_id": run_id,
        "operation": WORKING_MEMORY_OPERATION,
        "status": status,
        "generated_at": generated_at,
        "window_started_at": window_started_at,
        "window_hours": WORKING_MEMORY_WINDOW_HOURS,
        "trigger": trigger,
        "project_id": project.identity.project_id,
        "project": project.name,
        "repo_path": str(project.identity.repo_path),
        "recent_versions_considered": len(data.versions),
        "records_included": len(record_ids),
        "included_record_ids": list(record_ids),
        "changed_records_since_previous": changed_records_since_previous,
        "current_file": str(current_file),
        "run_folder": str(run_folder),
    }


def working_memory_status(
    *,
    config: Config,
    store: ContextStore,
    project: ContextBriefProject,
) -> WorkingMemoryStatus:
    """Compute current Working Memory freshness and availability."""
    paths = working_memory_paths(config, project.identity.project_id)
    manifest = read_manifest(paths.current_manifest) or {}
    generated_at = str(manifest.get("generated_at") or "").strip() or None
    window_hours = int(manifest.get("window_hours") or WORKING_MEMORY_WINDOW_HOURS)
    changed = count_changed_records_since(
        store,
        project_id=project.identity.project_id,
        since=generated_at,
    )
    raw_included_ids = manifest.get("included_record_ids") or []
    included_ids = raw_included_ids if isinstance(raw_included_ids, list) else []
    missing = count_missing_included_records(
        store,
        project_id=project.identity.project_id,
        record_ids=[str(record_id) for record_id in included_ids],
    )
    age = age_seconds_since(generated_at)
    file_exists = paths.current_file.is_file()
    manifest_exists = paths.current_manifest.is_file()
    if not file_exists:
        availability = "missing"
        action = "Run `lerim working-memory refresh`."
    elif not manifest_exists:
        availability = "error"
        action = "Run `lerim working-memory refresh --force`."
    elif missing > 0:
        availability = "stale"
        action = "Refresh because this Working Memory cites records no longer present in the live DB."
    elif changed > 0:
        availability = "stale"
        action = "Refresh if newest short-term DB context matters."
    elif age is None or age > window_hours * 3600:
        availability = "stale"
        action = "Refresh because the short-term memory window has moved."
    else:
        availability = "available"
        action = "Continue with this recent memory; use Context Brief for long-term context."
    return WorkingMemoryStatus(
        availability=availability,
        project=project.name,
        project_id=project.identity.project_id,
        repo_path=str(project.identity.repo_path),
        generated_at=generated_at,
        age_seconds=age,
        window_hours=window_hours,
        window_started_at=str(manifest.get("window_started_at") or "") or None,
        recent_versions_considered=int(manifest.get("recent_versions_considered") or 0),
        records_included=int(manifest.get("records_included") or 0),
        records_changed_since_generation=changed,
        records_missing_since_generation=missing,
        current_file=str(paths.current_file),
        current_manifest=str(paths.current_manifest),
        latest_run_folder=str(manifest.get("run_folder") or "") or None,
        suggested_action=action,
    )


def write_current_working_memory_artifacts(
    *,
    paths: WorkingMemoryPaths,
    run_markdown: Path,
    run_manifest: Path,
) -> None:
    """Copy dated Working Memory artifacts into the stable current location."""
    paths.current_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(run_markdown, paths.current_file)
    shutil.copyfile(run_manifest, paths.current_manifest)


def working_memory_status_to_dict(status: WorkingMemoryStatus) -> dict[str, Any]:
    """Convert Working Memory status to a JSON-ready dict."""
    payload = asdict(status)
    payload["age"] = human_age(status.age_seconds)
    return payload


def _append_record_id(ordered: list[str], seen: set[str], value: Any) -> None:
    """Append one normalized record ID once."""
    record_id = str(value or "").strip()
    if record_id and record_id not in seen:
        seen.add(record_id)
        ordered.append(record_id)


__all__ = [
    "WORKING_MEMORY_FILENAME",
    "WORKING_MEMORY_MANIFEST_FILENAME",
    "WORKING_MEMORY_OPERATION",
    "WORKING_MEMORY_WINDOW_HOURS",
    "WorkingMemoryData",
    "WorkingMemoryPaths",
    "WorkingMemoryStatus",
    "build_working_memory_manifest",
    "load_working_memory_data",
    "load_recent_record_versions",
    "working_memory_paths",
    "working_memory_record_ids",
    "working_memory_status",
    "working_memory_status_to_dict",
    "working_memory_window_start",
    "write_current_working_memory_artifacts",
]
