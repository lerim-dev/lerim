"""DSPy Run Clinic pipeline over project context records and activity metrics."""

from __future__ import annotations

import json
from contextlib import nullcontext
from typing import Any

from lerim.agents.dspy_compat import dspy
from lerim.agents.model_helpers import call_model_step, prediction_payload
from lerim.agents.model_runtime import ModelRuntime, build_model_runtime
from lerim.agents.run_clinic.schemas import RunClinicReportOutput
from lerim.agents.run_clinic.signatures import CompileRunClinic
from lerim.config.settings import Config
from lerim.context import ContextStore
from lerim.context_brief import ContextBriefProject
from lerim.run_clinic import (
    RunClinicData,
    build_empty_run_clinic_report,
    load_run_clinic_data,
    run_clinic_record_ids,
)

RUN_INSTRUCTION = (
    "Diagnose recurring project patterns from Lerim context evidence. Produce a "
    "human-facing Clinic report with findings, recommendations, questions, and "
    "no invented live workspace state."
)


class RunClinicPipeline(dspy.Module):
    """Load project evidence, compile a diagnostic report, and return metadata."""

    def __init__(
        self,
        *,
        store: ContextStore,
        project: ContextBriefProject,
        config: Config,
        window_started_at: str,
        runtime: ModelRuntime | None = None,
        compile_step: Any | None = None,
    ) -> None:
        """Create the Run Clinic pipeline."""
        super().__init__()
        self.store = store
        self.project = project
        self.config = config
        self.window_started_at = window_started_at
        self.runtime = runtime
        self.adapter = dspy.JSONAdapter()
        self.uses_real_model = compile_step is None
        self.compile_step = compile_step or dspy.Predict(CompileRunClinic)

    def forward(self) -> dict[str, Any]:
        """Run evidence loading and model-backed Clinic diagnosis."""
        data = load_run_clinic_data(
            self.store,
            project_id=self.project.identity.project_id,
            since=self.window_started_at,
        )
        valid_ids = set(run_clinic_record_ids(data))
        events: list[dict[str, Any]] = [
            {
                "kind": "load_clinic_evidence",
                "records": len(data.records),
                "versions": len(data.versions),
                "sessions": len(data.sessions),
            }
        ]
        if data.records:
            with self.model_context():
                output, retry_events, attempts = call_model_step(
                    lambda instruction: self.compile_step(
                        run_instruction=instruction,
                        project_json=json.dumps(project_payload(self.project), ensure_ascii=True),
                        metrics_json=json.dumps(data.metrics, ensure_ascii=True),
                        records_json=json.dumps(record_payloads(data.records), ensure_ascii=True),
                        versions_json=json.dumps(version_payloads(data.versions), ensure_ascii=True),
                        sessions_json=json.dumps(session_payloads(data.sessions), ensure_ascii=True),
                    ),
                    stage="compile_run_clinic",
                    progress=False,
                    progress_label="run-clinic",
                    run_instruction=RUN_INSTRUCTION,
                    validate_result=lambda result: validate_clinic_output(
                        result,
                        valid_record_ids=valid_ids,
                    ),
                    make_observation=model_event,
                    semantic_retry_content=clinic_retry_content,
                    validation_retry_target="complete corrected Run Clinic",
                    raise_on_validation_failure=False,
                )
            report = sanitize_report(
                report_from_output(output, data=data),
                data=data,
                valid_record_ids=valid_ids,
            )
            events.extend(retry_events)
            events.append(
                {
                    "kind": "model_step",
                    "stage": "compile_run_clinic",
                    "attempts": attempts,
                    "record_count": len(data.records),
                }
            )
        else:
            report = build_empty_run_clinic_report(data)
        return {
            "data": data,
            "report": report,
            "record_ids": run_clinic_record_ids(data, report),
            "events": events,
            "done": True,
        }

    def model_context(self):
        """Return a DSPy context only when real predictors need a configured LM."""
        if not self.uses_real_model:
            return nullcontext()
        if self.runtime is None:
            self.runtime = build_model_runtime(config=self.config)
        return dspy.context(lm=self.runtime.lm, adapter=self.adapter)


def project_payload(project: ContextBriefProject) -> dict[str, Any]:
    """Return compact project metadata for the Clinic compiler."""
    return {
        "name": project.name,
        "project_id": project.identity.project_id,
        "repo_path": str(project.identity.repo_path),
    }


def record_payloads(records: tuple[dict[str, Any], ...]) -> list[dict[str, Any]]:
    """Return bounded record fields for Run Clinic diagnosis."""
    return [
        {
            "record_id": record.get("record_id"),
            "kind": record.get("kind"),
            "record_role": record.get("record_role"),
            "title": record.get("title"),
            "body": record.get("body"),
            "decision": record.get("decision"),
            "why": record.get("why"),
            "user_intent": record.get("user_intent"),
            "what_happened": record.get("what_happened"),
            "outcomes": record.get("outcomes"),
            "updated_at": record.get("updated_at"),
        }
        for record in records
    ]


def version_payloads(versions: tuple[dict[str, Any], ...]) -> list[dict[str, Any]]:
    """Return compact recent version metadata."""
    return [
        {
            "record_id": version.get("record_id"),
            "version_no": version.get("version_no"),
            "change_kind": version.get("change_kind"),
            "kind": version.get("kind"),
            "record_role": version.get("record_role"),
            "title": version.get("title"),
            "changed_at": version.get("changed_at"),
        }
        for version in versions[:80]
    ]


def session_payloads(sessions: tuple[dict[str, Any], ...]) -> list[dict[str, Any]]:
    """Return compact recent session metadata."""
    return [
        {
            "session_id": session.get("session_id"),
            "source_name": session.get("source_name"),
            "created_at": session.get("created_at"),
            "message_count": session.get("message_count"),
            "tool_call_count": session.get("tool_call_count"),
            "error_count": session.get("error_count"),
        }
        for session in sessions[:60]
    ]


def report_from_output(output: Any, *, data: RunClinicData) -> dict[str, Any]:
    """Convert model output into a JSON-ready report."""
    payload = clinic_payload(output)
    report = RunClinicReportOutput.model_validate(payload).model_dump(mode="json")
    report["readiness_score"] = max(
        0,
        min(100, int(report.get("readiness_score") or data.metrics["readiness_score"])),
    )
    report["metrics"] = data.metrics
    return report


def sanitize_report(
    report: dict[str, Any],
    *,
    data: RunClinicData,
    valid_record_ids: set[str],
) -> dict[str, Any]:
    """Drop uncited model items and add a conservative cited fallback when needed."""
    sanitized = dict(report)
    sanitized["findings"] = sanitize_cited_items(
        report.get("findings") or [],
        valid_record_ids=valid_record_ids,
    )
    sanitized["recommended_actions"] = sanitize_cited_items(
        report.get("recommended_actions") or [],
        valid_record_ids=valid_record_ids,
    )
    if data.records and not sanitized["findings"] and not sanitized["recommended_actions"]:
        first_record = data.records[0]
        record_id = str(first_record.get("record_id") or "")
        title = str(first_record.get("title") or "Clinic evidence requires review")
        sanitized["findings"] = [
            {
                "title": "Clinic evidence needs manual review",
                "pattern_type": "evidence_gap",
                "severity": "medium",
                "confidence": "low",
                "summary": f"The model did not produce a validated diagnosis, but `{title}` is available as cited Clinic evidence.",
                "why_it_matters": "Run Clinic refuses to show uncited diagnosis items.",
                "evidence_record_ids": [record_id],
            }
        ]
    sanitized["metrics"] = data.metrics
    return sanitized


def sanitize_cited_items(
    items: list[Any],
    *,
    valid_record_ids: set[str],
) -> list[dict[str, Any]]:
    """Keep only report items with at least one valid evidence record ID."""
    kept: list[dict[str, Any]] = []
    for item in items:
        payload = prediction_payload(item)
        ids = [
            record_id
            for record_id in [str(value).strip() for value in payload.get("evidence_record_ids") or []]
            if record_id in valid_record_ids
        ]
        if not ids:
            continue
        payload["evidence_record_ids"] = ids
        kept.append(payload)
    return kept


def validate_clinic_output(output: Any, *, valid_record_ids: set[str]) -> str | None:
    """Return a validation error when Clinic output cites unsupported records."""
    try:
        payload = clinic_payload(output)
        RunClinicReportOutput.model_validate(payload)
    except Exception as exc:
        return f"invalid_schema:{type(exc).__name__}:{exc}"
    for field_name in ("findings", "recommended_actions"):
        for item in payload.get(field_name) or []:
            item_payload = prediction_payload(item)
            ids = [str(value) for value in item_payload.get("evidence_record_ids") or []]
            if valid_record_ids and not ids:
                return f"run_clinic_{field_name}_missing_record_id"
            unknown = [record_id for record_id in ids if record_id not in valid_record_ids]
            if unknown:
                return f"run_clinic_unknown_record_id:{unknown[0]}"
    return None


def clinic_payload(output: Any) -> dict[str, Any]:
    """Return the report payload from DSPy predictions or dict test doubles."""
    if isinstance(output, dict) and "report" in output:
        return prediction_payload(output.get("report"))
    return prediction_payload(output, output_field="report")


def clinic_retry_content(error: str) -> str:
    """Return validation feedback for a Clinic compiler retry."""
    return (
        f"Validation failed: {error}. Return corrected JSON. "
        "Every finding and recommended action must cite exact evidence_record_ids "
        "from the supplied records or versions."
    )


def model_event(action: str, ok: bool, content: str, args: dict[str, Any]) -> dict[str, Any]:
    """Return one serializable model event."""
    return {"kind": action, "ok": ok, "content": content, **args}
