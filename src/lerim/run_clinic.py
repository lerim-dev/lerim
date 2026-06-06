"""Project Run Clinic artifacts for trend, risk, and improvement analysis."""

from __future__ import annotations

import json
import shutil
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

RUN_CLINIC_FILENAME = "RUN_CLINIC.md"
RUN_CLINIC_REPORT_FILENAME = "RUN_CLINIC.report.json"
RUN_CLINIC_MANIFEST_FILENAME = "RUN_CLINIC.manifest.json"
RUN_CLINIC_OPERATION = "run-clinic"
RUN_CLINIC_WINDOW_DAYS = 30
RUN_CLINIC_RECORD_LIMIT = 120
RUN_CLINIC_VERSION_LIMIT = 300
RUN_CLINIC_SESSION_LIMIT = 200
RUN_CLINIC_FRESH_HOURS = 24
RUN_CLINIC_LINE_LIMIT = 180

ROLE_STAGE_MAP = {
    "preference": "scope",
    "constraint": "scope",
    "procedure": "execution",
    "state_change": "execution",
    "artifact": "handoff",
    "gotcha": "debugging",
    "failure_mode": "debugging",
    "eval_asset": "verification",
    "general": "context",
}


@dataclass(frozen=True)
class RunClinicPaths:
    """Stable current Run Clinic artifact paths for one project."""

    current_dir: Path
    current_file: Path
    current_manifest: Path
    current_report: Path


@dataclass(frozen=True)
class RunClinicData:
    """Evidence loaded for one Run Clinic generation."""

    records: tuple[dict[str, Any], ...]
    versions: tuple[dict[str, Any], ...]
    sessions: tuple[dict[str, Any], ...]
    metrics: dict[str, Any]


@dataclass(frozen=True)
class RunClinicStatus:
    """Freshness and availability metadata for one project's Run Clinic."""

    availability: str
    project: str
    project_id: str
    repo_path: str
    generated_at: str | None
    age_seconds: int | None
    window_days: int
    window_started_at: str | None
    records_included: int
    records_considered: int
    recent_versions_considered: int
    sessions_considered: int
    records_changed_since_generation: int
    records_missing_since_generation: int
    current_file: str
    current_manifest: str
    current_report: str
    latest_run_folder: str | None
    suggested_action: str


def run_clinic_paths(config: Config, project_id: str) -> RunClinicPaths:
    """Return stable current Run Clinic paths for a project."""
    current_dir = config.global_data_dir / "workspace" / "current" / project_id
    return RunClinicPaths(
        current_dir=current_dir,
        current_file=current_dir / RUN_CLINIC_FILENAME,
        current_manifest=current_dir / RUN_CLINIC_MANIFEST_FILENAME,
        current_report=current_dir / RUN_CLINIC_REPORT_FILENAME,
    )


def run_clinic_window_start(
    *,
    now: datetime | None = None,
    window_days: int = RUN_CLINIC_WINDOW_DAYS,
) -> str:
    """Return the lower timestamp bound for Run Clinic trend evidence."""
    effective_now = now or datetime.now(timezone.utc)
    if effective_now.tzinfo is None:
        effective_now = effective_now.replace(tzinfo=timezone.utc)
    start = effective_now.astimezone(timezone.utc) - timedelta(days=max(1, int(window_days)))
    return start.isoformat()


def load_run_clinic_data(
    store: ContextStore,
    *,
    project_id: str,
    since: str,
) -> RunClinicData:
    """Load records, versions, sessions, and deterministic metrics for Run Clinic."""
    records_payload = store.query(
        entity="records",
        mode="list",
        project_ids=[project_id],
        status="active",
        order_by="updated_at",
        limit=RUN_CLINIC_RECORD_LIMIT,
        include_total=True,
    )
    archived_payload = store.query(
        entity="records",
        mode="count",
        project_ids=[project_id],
        status="archived",
    )
    all_records_payload = store.query(
        entity="records",
        mode="count",
        project_ids=[project_id],
        include_archived=True,
    )
    versions_payload = store.query(
        entity="versions",
        mode="list",
        project_ids=[project_id],
        updated_since=since,
        order_by="updated_at",
        limit=RUN_CLINIC_VERSION_LIMIT,
        include_total=True,
    )
    sessions_payload = store.query(
        entity="sessions",
        mode="list",
        project_ids=[project_id],
        created_since=since,
        order_by="created_at",
        limit=RUN_CLINIC_SESSION_LIMIT,
        include_total=True,
    )
    records = tuple(records_payload.get("rows") or ())
    versions = tuple(versions_payload.get("rows") or ())
    sessions = tuple(sessions_payload.get("rows") or ())
    return RunClinicData(
        records=records,
        versions=versions,
        sessions=sessions,
        metrics=build_run_clinic_metrics(
            records=records,
            versions=versions,
            sessions=sessions,
            total_records=int(records_payload.get("total") or len(records)),
            archived_records=int(archived_payload.get("count") or 0),
            all_records=int(all_records_payload.get("count") or len(records)),
            total_versions=int(versions_payload.get("total") or len(versions)),
            total_sessions=int(sessions_payload.get("total") or len(sessions)),
        ),
    )


def build_run_clinic_metrics(
    *,
    records: tuple[dict[str, Any], ...],
    versions: tuple[dict[str, Any], ...],
    sessions: tuple[dict[str, Any], ...],
    total_records: int,
    archived_records: int,
    all_records: int,
    total_versions: int,
    total_sessions: int,
) -> dict[str, Any]:
    """Build deterministic trend metrics without inspecting user wording."""
    kind_counts: dict[str, int] = {}
    role_counts: dict[str, int] = {}
    stage_scores: dict[str, int] = {}
    change_days: dict[str, int] = {}
    for record in records:
        kind = str(record.get("kind") or "unknown")
        role = str(record.get("record_role") or "general")
        kind_counts[kind] = kind_counts.get(kind, 0) + 1
        role_counts[role] = role_counts.get(role, 0) + 1
        stage = ROLE_STAGE_MAP.get(role, "context")
        stage_scores[stage] = stage_scores.get(stage, 0) + 1
    for version in versions:
        changed_at = str(version.get("changed_at") or version.get("updated_at") or "")
        day = changed_at[:10] if len(changed_at) >= 10 else "unknown"
        change_days[day] = change_days.get(day, 0) + 1
    session_totals = {
        "messages": sum(int(session.get("message_count") or 0) for session in sessions),
        "tool_calls": sum(int(session.get("tool_call_count") or 0) for session in sessions),
        "errors": sum(int(session.get("error_count") or 0) for session in sessions),
        "tokens": sum(int(session.get("total_tokens") or 0) for session in sessions),
    }
    evidence_count = len(records) + len(versions) + len(sessions)
    readiness = min(
        100,
        20
        + min(35, len(records) * 6)
        + min(25, len(versions) * 2)
        + min(20, len(sessions) * 2),
    )
    if not records:
        readiness = 0
    return {
        "active_records_sampled": len(records),
        "active_records_total": total_records,
        "archived_records_total": archived_records,
        "all_records_total": all_records,
        "recent_versions_sampled": len(versions),
        "recent_versions_total": total_versions,
        "recent_sessions_sampled": len(sessions),
        "recent_sessions_total": total_sessions,
        "evidence_items": evidence_count,
        "readiness_score": readiness,
        "kind_counts": kind_counts,
        "role_counts": role_counts,
        "stage_scores": stage_scores,
        "changes_by_day": sorted(
            [{"date": key, "changes": value} for key, value in change_days.items()],
            key=lambda item: item["date"],
        ),
        "session_totals": session_totals,
    }


def run_clinic_record_ids(data: RunClinicData, report: dict[str, Any] | None = None) -> tuple[str, ...]:
    """Return unique record IDs cited by the Clinic evidence and report."""
    ordered: list[str] = []
    seen: set[str] = set()
    for record in data.records:
        append_record_id(ordered, seen, record.get("record_id"))
    for version in data.versions:
        append_record_id(ordered, seen, version.get("record_id"))
    for item in ((report or {}).get("findings") or []):
        for record_id in item.get("evidence_record_ids") or []:
            append_record_id(ordered, seen, record_id)
    for item in ((report or {}).get("recommended_actions") or []):
        for record_id in item.get("evidence_record_ids") or []:
            append_record_id(ordered, seen, record_id)
    return tuple(ordered)


def build_empty_run_clinic_report(data: RunClinicData) -> dict[str, Any]:
    """Return a report for projects without enough persisted evidence."""
    return {
        "headline": "Run Clinic has no project evidence yet.",
        "readiness_score": data.metrics["readiness_score"],
        "summary": [
            "Lerim has not accumulated active context records for this project yet."
        ],
        "findings": [],
        "recommended_actions": [
            {
                "title": "Import or ingest source sessions first",
                "action_type": "ingest",
                "priority": "high",
                "summary": "Clinic needs persisted records before it can diagnose recurring patterns.",
                "evidence_record_ids": [],
            }
        ],
        "questions": [],
        "metrics": data.metrics,
    }


def render_run_clinic_markdown(
    *,
    project: ContextBriefProject,
    generated_at: str,
    window_started_at: str,
    previous_generated_at: str | None,
    generation_trigger: str,
    data: RunClinicData,
    report: dict[str, Any],
    current_file: Path | None,
    run_folder: Path | None,
) -> str:
    """Render Run Clinic report markdown from structured report data."""
    lines = [
        "# Run Clinic",
        "",
        "Project-level diagnostic view of recurring context patterns, risks, and improvement opportunities.",
        "",
        "## Metadata",
        "",
        f"- project: `{project.name}`",
        f"- project_id: `{project.identity.project_id}`",
        f"- repo_path: `{project.identity.repo_path}`",
        f"- generated_at: `{generated_at}`",
        f"- window_started_at: `{window_started_at}`",
        f"- previous_generated_at: `{previous_generated_at or 'none'}`",
        f"- trigger: `{generation_trigger}`",
        f"- current_file: `{current_file}`" if current_file else "- current_file: `none`",
        f"- run_folder: `{run_folder}`" if run_folder else "- run_folder: `none`",
        "",
        "## Diagnosis",
        "",
        f"Readiness score: `{int(report.get('readiness_score') or data.metrics.get('readiness_score') or 0)}`",
        "",
        str(report.get("headline") or "No diagnosis generated."),
        "",
        "## Summary",
        "",
    ]
    lines.extend(markdown_bullets(report.get("summary") or []))
    lines.extend(["", "## Findings", ""])
    findings = report.get("findings") or []
    if findings:
        for item in findings:
            lines.extend(
                [
                    f"### {str(item.get('title') or 'Finding')}",
                    "",
                    f"- severity: `{item.get('severity') or 'medium'}`",
                    f"- pattern_type: `{item.get('pattern_type') or 'pattern'}`",
                    f"- confidence: `{item.get('confidence') or 'medium'}`",
                    f"- evidence_record_ids: `{', '.join(item.get('evidence_record_ids') or [])}`",
                    "",
                    str(item.get("summary") or ""),
                    "",
                    str(item.get("why_it_matters") or ""),
                    "",
                ]
            )
    else:
        lines.append("No recurring pattern finding was generated.")
    lines.extend(["", "## Recommended Actions", ""])
    actions = report.get("recommended_actions") or []
    if actions:
        for item in actions:
            lines.extend(
                [
                    f"### {str(item.get('title') or 'Action')}",
                    "",
                    f"- priority: `{item.get('priority') or 'medium'}`",
                    f"- action_type: `{item.get('action_type') or 'improvement'}`",
                    f"- evidence_record_ids: `{', '.join(item.get('evidence_record_ids') or [])}`",
                    "",
                    str(item.get("summary") or ""),
                    "",
                ]
            )
    else:
        lines.append("No recommended action was generated.")
    lines.extend(["", "## Questions", ""])
    lines.extend(markdown_bullets(report.get("questions") or []))
    lines.extend(["", "## Metrics", "", "```json", json.dumps(data.metrics, indent=2, ensure_ascii=True), "```"])
    return "\n".join(lines[:RUN_CLINIC_LINE_LIMIT]).rstrip() + "\n"


def markdown_bullets(items: Any) -> list[str]:
    """Render a JSON list as markdown bullets."""
    values = [str(item).strip() for item in items if str(item).strip()]
    if not values:
        return ["No generated entries."]
    return [f"- {value}" for value in values]


def build_run_clinic_manifest(
    *,
    run_id: str,
    status: str,
    generated_at: str,
    window_started_at: str,
    project: ContextBriefProject,
    data: RunClinicData,
    report: dict[str, Any],
    changed_records_since_previous: int,
    trigger: str,
    current_file: Path,
    current_report: Path,
    run_folder: Path,
) -> dict[str, Any]:
    """Build the Run Clinic manifest payload."""
    record_ids = run_clinic_record_ids(data, report)
    return {
        "run_id": run_id,
        "operation": RUN_CLINIC_OPERATION,
        "status": status,
        "generated_at": generated_at,
        "window_started_at": window_started_at,
        "window_days": RUN_CLINIC_WINDOW_DAYS,
        "trigger": trigger,
        "project_id": project.identity.project_id,
        "project": project.name,
        "repo_path": str(project.identity.repo_path),
        "records_considered": len(data.records),
        "records_included": len(record_ids),
        "recent_versions_considered": len(data.versions),
        "sessions_considered": len(data.sessions),
        "included_record_ids": list(record_ids),
        "changed_records_since_previous": changed_records_since_previous,
        "current_file": str(current_file),
        "current_report": str(current_report),
        "run_folder": str(run_folder),
    }


def run_clinic_status(
    *,
    config: Config,
    store: ContextStore,
    project: ContextBriefProject,
) -> RunClinicStatus:
    """Compute current Run Clinic freshness and availability."""
    paths = run_clinic_paths(config, project.identity.project_id)
    manifest = read_manifest(paths.current_manifest) or {}
    generated_at = str(manifest.get("generated_at") or "").strip() or None
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
    report_exists = paths.current_report.is_file()
    if not file_exists or not report_exists:
        availability = "missing"
        action = "Run `lerim clinic refresh`."
    elif not manifest_exists:
        availability = "error"
        action = "Run `lerim clinic refresh --force`."
    elif missing > 0:
        availability = "stale"
        action = "Refresh because this Clinic cites records no longer present in the live DB."
    elif changed > 0:
        availability = "stale"
        action = "Refresh to include the latest context changes."
    elif age is None or age > RUN_CLINIC_FRESH_HOURS * 3600:
        availability = "stale"
        action = "Refresh because the Clinic trend window has moved."
    else:
        availability = "available"
        action = "Use this Clinic for project-level diagnosis and improvement planning."
    return RunClinicStatus(
        availability=availability,
        project=project.name,
        project_id=project.identity.project_id,
        repo_path=str(project.identity.repo_path),
        generated_at=generated_at,
        age_seconds=age,
        window_days=int(manifest.get("window_days") or RUN_CLINIC_WINDOW_DAYS),
        window_started_at=str(manifest.get("window_started_at") or "") or None,
        records_included=int(manifest.get("records_included") or 0),
        records_considered=int(manifest.get("records_considered") or 0),
        recent_versions_considered=int(manifest.get("recent_versions_considered") or 0),
        sessions_considered=int(manifest.get("sessions_considered") or 0),
        records_changed_since_generation=changed,
        records_missing_since_generation=missing,
        current_file=str(paths.current_file),
        current_manifest=str(paths.current_manifest),
        current_report=str(paths.current_report),
        latest_run_folder=str(manifest.get("run_folder") or "") or None,
        suggested_action=action,
    )


def run_clinic_status_to_dict(status: RunClinicStatus) -> dict[str, Any]:
    """Convert Run Clinic status to a JSON-ready dict."""
    payload = asdict(status)
    payload["age"] = human_age(status.age_seconds)
    return payload


def write_current_run_clinic_artifacts(
    *,
    paths: RunClinicPaths,
    run_markdown: Path,
    run_manifest: Path,
    run_report: Path,
) -> None:
    """Copy dated Run Clinic artifacts into the stable current location."""
    paths.current_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(run_markdown, paths.current_file)
    shutil.copyfile(run_manifest, paths.current_manifest)
    shutil.copyfile(run_report, paths.current_report)


def append_record_id(ordered: list[str], seen: set[str], value: Any) -> None:
    """Append one normalized record ID once."""
    record_id = str(value or "").strip()
    if record_id and record_id not in seen:
        seen.add(record_id)
        ordered.append(record_id)


__all__ = [
    "RUN_CLINIC_FILENAME",
    "RUN_CLINIC_FRESH_HOURS",
    "RUN_CLINIC_MANIFEST_FILENAME",
    "RUN_CLINIC_OPERATION",
    "RUN_CLINIC_REPORT_FILENAME",
    "RUN_CLINIC_WINDOW_DAYS",
    "RunClinicData",
    "RunClinicPaths",
    "RunClinicStatus",
    "build_empty_run_clinic_report",
    "build_run_clinic_manifest",
    "load_run_clinic_data",
    "render_run_clinic_markdown",
    "run_clinic_paths",
    "run_clinic_record_ids",
    "run_clinic_status",
    "run_clinic_status_to_dict",
    "run_clinic_window_start",
    "write_current_run_clinic_artifacts",
]
