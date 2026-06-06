"""DSPy signatures for Run Clinic diagnosis."""

from __future__ import annotations

from lerim.agents.dspy_compat import dspy
from lerim.agents.run_clinic.schemas import RunClinicReportOutput


class CompileRunClinic(dspy.Signature):
    """You are Lerim's Run Clinic compiler. Diagnose recurring project patterns from persisted context records and recent activity.
    Return only structured output. Do not include <think> tags, hidden reasoning, markdown, or prose.

    Rules:
    - Use only the supplied records, versions, sessions, and metrics.
    - Run Clinic is not startup memory. Context Brief is long-term startup context; Working Memory is short-term continuation context.
    - Run Clinic is a project diagnostic for a human: recurring friction, context gaps, strengths, verification gaps, and improvement opportunities.
    - Every finding and recommended action must include at least one exact record_id copied from the supplied records or versions when evidence exists.
    - Put record IDs only in evidence_record_ids, never in text.
    - Do not create tasks from thin evidence. If evidence is sparse, say what cannot be diagnosed yet.
    - Prefer patterns that change future behavior, UI, workflow, skills, evals, or project memory quality.
    - Do not invent live workspace state, user goals, tests, or current bugs beyond supplied evidence.
    - Do not use raw keyword counts or wording tricks. Interpret the structured records and metrics.
    - Keep findings to 3-5 items, recommended_actions to 3-5 items, questions to at most 3.
    """

    run_instruction: str = dspy.InputField(desc="RUN INSTRUCTION")
    project_json: str = dspy.InputField(desc="PROJECT JSON")
    metrics_json: str = dspy.InputField(desc="DETERMINISTIC METRICS JSON")
    records_json: str = dspy.InputField(desc="ACTIVE RECORDS JSON")
    versions_json: str = dspy.InputField(desc="RECENT RECORD VERSIONS JSON")
    sessions_json: str = dspy.InputField(desc="RECENT SESSIONS JSON")
    report: RunClinicReportOutput = dspy.OutputField(desc="Evidence-backed Run Clinic report")
