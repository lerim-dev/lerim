"""DSPy signatures for Working Memory compilation."""

from __future__ import annotations

from lerim.agents.dspy_compat import dspy
from lerim.agents.working_memory.schemas import WorkingMemoryDraftOutput


class CompileWorkingMemory(dspy.Signature):
    """You are Lerim's Working Memory compiler. Compile a short-term continuation handoff from recent persisted context changes.
    Return only structured output. Do not include <think> tags, hidden reasoning, markdown, or prose.

    Rules:
    - Use only the supplied records and generation context.
    - Working Memory is continuation context, not a task list.
    - Do not invent next actions. The next user prompt decides the task.
    - Every non-empty line must include at least one exact record_id copied from the supplied records.
    - Put record IDs only in record_ids, never in text.
    - Prefer current active records over superseded or archived records.
    - When a record was superseded, explain the current replacement rather than repeating the old record as truth.
    - Include open_questions only when a recent record explicitly supports an unresolved continuation question.
    - Include continuation_handoff only when recent episode or replacement evidence supports where a resumed thread should start.
    - Mention workspace snapshot only through current_state, and say it is generation-time state that can go stale.
    - Select the useful short-term context. Do not enumerate every supplied record.
    - Maximum lines: current_state 3, completed_recently 5, changed_context 6, current_decisions 5, current_constraints 5, current_facts 5, recent_episode_evidence 4, open_questions 3, continuation_handoff 5.
    """

    run_instruction: str = dspy.InputField(desc="RUN INSTRUCTION")
    project_json: str = dspy.InputField(desc="PROJECT JSON")
    recent_changes_json: str = dspy.InputField(desc="RECENT CHANGES JSON")
    current_records_json: str = dspy.InputField(desc="CURRENT RECORDS JSON")
    replacements_json: str = dspy.InputField(desc="SUPERSEDED RECORD REPLACEMENTS JSON")
    workspace_snapshot_json: str = dspy.InputField(desc="GENERATION-TIME WORKSPACE SNAPSHOT JSON")
    generation_context_json: str = dspy.InputField(desc="WORKING MEMORY GENERATION CONTEXT JSON")
    memory: WorkingMemoryDraftOutput = dspy.OutputField(
        desc="Short-term Working Memory handoff"
    )
