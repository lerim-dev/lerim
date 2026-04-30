"""LLM synthesis adapter for generated Working Memory artifacts."""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models import Model
from pydantic_ai.usage import UsageLimits

from lerim.agents.mlflow_observability import handle_mlflow_event_stream, mlflow_span
from lerim.agents.model_settings import LOW_VARIANCE_AGENT_MODEL_SETTINGS
from lerim.working_memory import MemoryLine, WorkingMemoryDraft


WORKING_MEMORY_SYSTEM_PROMPT = """\
<role>
You write Lerim Working Memory for coding agents.
</role>

<rules>
- Use only the candidate records supplied in the prompt.
- Optimize for a coding agent starting work in this repository right now.
- Prefer actionability over completeness: include what changes decisions, commands, file paths, constraints, or next steps.
- Prefer durable records: decision, preference, constraint, fact, reference.
- Use episode records for recent flow context, current work, open loops, and next commands.
- If a record is a decision or fact, present it as established context, not as unfinished current work.
- Produce the fixed fields: summary, start_here, current_handoff, decisions, constraints_preferences, project_facts, open_risks, follow_up_queries.
- Every fixed field is a list of objects with text and record_ids. Use an empty list when records do not support a field.
- Do not create Current Handoff, Open Risks, Next Steps, Open Concerns, or todo wording unless a cited candidate record explicitly supports unresolved, blocked, risky, requested-next, or recently-in-progress work.
- Never say `lerim working-memory show` generates Working Memory. `show` only reads the current artifact. Generation happens through `refresh`, the daily daemon pass, or maintain-triggered refresh.
- Avoid implementation minutiae unless they prevent mistakes or guide the next edit.
- Make the summary a prioritized startup cache, not a table of contents.
- If there are episode records, put the newest recent-flow or handoff fact first in the summary.
- Treat test/build results from records as historical evidence with timestamps, not as current truth. Any line mentioning test, build, lint, typecheck, CI, or verification results must say "Persisted record says ..." and "rerun relevant tests after edits."
- Avoid repeating the same memory across fields.
- Keep the result compact enough for a roughly 50-line markdown file.
- Every line must include at least one exact record_id from the supplied candidates.
- record_ids must copy exact record_id strings from the candidate records; do not alter, normalize, shorten, or invent them.
- Put record IDs only in the record_ids field, never in line text.
- Do not quote long evidence. Compress and preserve the practical instruction or fact.
- Do not invent current repository state beyond the stored records.
</rules>
"""


class WorkingMemoryLineOutput(BaseModel):
    """One cited line in the generated Working Memory draft."""

    text: str = Field(description="Compact memory statement without citations")
    record_ids: list[str] = Field(description="Exact source record IDs")


class WorkingMemoryOutput(BaseModel):
    """Structured output returned by the Working Memory synthesis agent."""

    summary: list[WorkingMemoryLineOutput] = Field(default_factory=list)
    start_here: list[WorkingMemoryLineOutput] = Field(default_factory=list)
    current_handoff: list[WorkingMemoryLineOutput] = Field(default_factory=list)
    decisions: list[WorkingMemoryLineOutput] = Field(default_factory=list)
    constraints_preferences: list[WorkingMemoryLineOutput] = Field(default_factory=list)
    project_facts: list[WorkingMemoryLineOutput] = Field(default_factory=list)
    open_risks: list[WorkingMemoryLineOutput] = Field(default_factory=list)
    follow_up_queries: list[WorkingMemoryLineOutput] = Field(default_factory=list)


def _candidate_for_prompt(record: dict[str, Any]) -> dict[str, Any]:
    """Return the compact candidate fields shown to the model."""
    return {
        "record_id": record.get("record_id"),
        "kind": record.get("kind"),
        "title": record.get("title"),
        "body": record.get("body"),
        "decision": record.get("decision"),
        "why": record.get("why"),
        "user_intent": record.get("user_intent"),
        "what_happened": record.get("what_happened"),
        "outcomes": record.get("outcomes"),
        "updated_at": record.get("updated_at"),
    }


def _candidate_profile(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Return compact metadata that frames what the records can support."""
    kind_counts: dict[str, int] = {}
    record_ids_by_kind: dict[str, list[str]] = {}
    newest_updated_at = ""
    newest_episode_updated_at = ""
    for record in records:
        kind = str(record.get("kind") or "unknown")
        kind_counts[kind] = kind_counts.get(kind, 0) + 1
        record_id = str(record.get("record_id") or "")
        if record_id:
            record_ids_by_kind.setdefault(kind, []).append(record_id)
        updated_at = str(record.get("updated_at") or "")
        newest_updated_at = max(newest_updated_at, updated_at)
        if kind == "episode":
            newest_episode_updated_at = max(newest_episode_updated_at, updated_at)
    episode_count = int(kind_counts.get("episode") or 0)
    episode_record_ids = record_ids_by_kind.get("episode", [])
    return {
        "candidate_count": len(records),
        "kind_counts": kind_counts,
        "record_ids_by_kind": record_ids_by_kind,
        "newest_updated_at": newest_updated_at or None,
        "newest_episode_updated_at": newest_episode_updated_at or None,
        "has_recent_flow_evidence": episode_count > 0,
        "current_handoff_evidence_record_ids": episode_record_ids,
        "guidance": (
            "Only populate current_handoff when cited records describe recent flow, "
            "current work, open loops, or next commands. Leave open_risks empty unless "
            "cited record text explicitly supports an unresolved risk, blocker, or "
            "requested follow-up. Treat all test/build results as historical persisted "
            "evidence and tell agents to rerun relevant checks after edits."
        ),
    }


def _memory_lines(lines: list[WorkingMemoryLineOutput]) -> tuple[MemoryLine, ...]:
    """Convert model line objects into draft memory lines."""
    return tuple(
        MemoryLine(text=line.text, record_ids=tuple(line.record_ids))
        for line in lines
    )


def _draft_from_output(output: WorkingMemoryOutput) -> WorkingMemoryDraft:
    """Build a fixed-section WorkingMemoryDraft from model output."""
    return WorkingMemoryDraft(
        summary=_memory_lines(output.summary),
        start_here=_memory_lines(output.start_here),
        current_handoff=_memory_lines(output.current_handoff),
        decisions=_memory_lines(output.decisions),
        constraints_preferences=_memory_lines(output.constraints_preferences),
        project_facts=_memory_lines(output.project_facts),
        open_risks=_memory_lines(output.open_risks),
        follow_up_queries=_memory_lines(output.follow_up_queries),
    )


def build_working_memory_agent(model: Model) -> Agent[None, WorkingMemoryOutput]:
    """Build the Working Memory synthesis agent."""
    return Agent(
        model,
        output_type=WorkingMemoryOutput,
        system_prompt=WORKING_MEMORY_SYSTEM_PROMPT,
        model_settings=LOW_VARIANCE_AGENT_MODEL_SETTINGS,
        retries=3,
        output_retries=2,
    )


def run_working_memory_synthesis(
    *,
    model: Model,
    candidates: list[dict[str, Any]],
    request_limit: int = 8,
    return_messages: bool = False,
) -> WorkingMemoryDraft | tuple[WorkingMemoryDraft, list[Any]]:
    """Run LLM synthesis over bounded candidate records."""
    agent = build_working_memory_agent(model)
    compact_candidates = [_candidate_for_prompt(record) for record in candidates]
    profile = _candidate_profile(candidates)
    prompt = (
        "Create a compact Working Memory from these candidate records for a coding "
        "agent starting a new session.\n"
        "Return the fixed fields summary, start_here, current_handoff, decisions, "
        "constraints_preferences, project_facts, open_risks, and follow_up_queries. "
        "Each field must be a list of {text, record_ids} objects.\n"
        "Return only cited lines using exact record_id values in record_ids.\n"
        "Do not place record IDs or citation syntax inside the line text.\n"
        "Prefer fields that answer: what matters now, what decisions are fixed, "
        "what constraints/preferences must be followed, what project facts prevent "
        "mistakes, and what to inspect next. Do not turn established decisions into "
        "todos or claim implementation status that is not present in the records.\n"
        "Keep current_handoff empty unless a cited record supports current or recent "
        "handoff evidence. Keep open_risks empty unless a cited record supports a "
        "real unresolved risk, blocker, or requested follow-up. If mentioning test, "
        "build, lint, typecheck, CI, or verification results, write them as "
        "historical persisted evidence with the wording \"Persisted record says ...\" "
        "and \"rerun relevant tests after edits.\"\n\n"
        f"Candidate profile JSON:\n{json.dumps(profile, ensure_ascii=True)}\n\n"
        f"Candidate records JSON:\n{json.dumps(compact_candidates, ensure_ascii=True)}"
    )
    with mlflow_span(
        "lerim.agent.working_memory",
        span_type="AGENT",
        attributes={"lerim.agent_name": "working_memory"},
        inputs={"candidate_count": len(compact_candidates)},
    ):
        result = agent.run_sync(
            prompt,
            usage_limits=UsageLimits(request_limit=max(1, int(request_limit))),
            event_stream_handler=handle_mlflow_event_stream,
        )
    draft = _draft_from_output(result.output)
    if return_messages:
        return draft, list(result.all_messages())
    return draft
