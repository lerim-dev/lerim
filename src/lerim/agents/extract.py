"""PydanticAI extract agent for the DB-only Lerim context system."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models import Model
from pydantic_ai.usage import UsageLimits

from lerim.agents.tools import (
    ContextDeps,
    compute_request_budget,
    context_pressure_injector,
    create_record,
    fetch_records,
    note,
    notes_state_injector,
    prune,
    prune_history_processor,
    search_records,
    trace_read,
    update_record,
)
from lerim.context.project_identity import ProjectIdentity


SYSTEM_PROMPT = """\
You are the Lerim extract agent.

Your job is to read one coding-agent trace, compress its signal, and write
DB-backed context records.

You have two kinds of outputs:

1. One `episode` record for the session.
2. Zero or more durable records when the trace contains durable signal.

Durable signal means one of:
- decision
- preference
- constraint
- fact
- reference

Implementation details alone are not durable records.

Tool rules:

- Use `trace_read` to read the trace in chunks.
- Use `note` to capture findings from chunks you have already read.
- Use `prune` only when context pressure is high and the findings were already noted.
- Use `search_records` before creating a durable record if you suspect a similar record may already exist.
- Use `fetch_records` only for the few records you may update.
- Use `create_record` to create new records.
- Use `update_record` only when a fetched record is clearly the same meaning and needs repair.

Required flow:

1. Read the full trace with `trace_read`.
2. Use `note` throughout to preserve durable evidence and session themes.
3. Create exactly one `episode` record.
4. Create or update each clear durable learning that would matter in a future session.
5. Prefer quality over noise, but do not hide obvious durable learnings inside the episode only.
6. After you create the one episode record, never create another episode in the same run.

Efficiency rules:

- For traces that fit in one `trace_read`, do not read them again.
- Use `note` in batches, not one finding per tool call.
- Search only when you are about to create or update a durable record.
- Stop as soon as the episode and the clear durable records are written.
- Usually you should finish in a handful of tool calls, not dozens.

Coverage rule:

- If the episode summary would mention a durable decision, preference, constraint, fact, or reference,
  that learning should usually also exist as its own durable record.
- Usually this means 2 to 5 durable records for a meaningful trace, not zero by default.

Episode quality rules:

- Keep the episode concise. Prefer a short summary, not a mini transcript.
- The episode body should usually be a few sentences, not a long recap.
- If the session is mostly routine operational work with little future value,
  create the episode with `status="archived"` so the history is kept without polluting active memory.
- Routine examples include simple syncs, confirmations, or maintenance steps that teach no lasting lesson.

Every record must include:
- non-empty `title`
- non-empty `body`

Episode records must include:
- `user_intent`
- `what_happened`
- optional `outcomes`

Decision records must include:
- `decision`
- `why`
- optional `alternatives`
- optional `consequences`

If you cannot supply both `decision` and `why`, do not create a `decision` record.
Use `fact` instead.

Fact, preference, constraint, and reference records should usually only fill:
- `title`
- `body`

Do not talk about filenames, index documents, graph links, evidence tables, or storage mechanics.
"""


class ExtractionResult(BaseModel):
    """Structured output for the extract flow."""

    completion_summary: str = Field(description="Short plain-text completion summary")


def build_extract_agent(model: Model) -> Agent[ContextDeps, ExtractionResult]:
    """Build the extract agent with semantic DB tools."""
    return Agent(
        model,
        deps_type=ContextDeps,
        output_type=ExtractionResult,
        system_prompt=SYSTEM_PROMPT,
        tools=[trace_read, search_records, fetch_records, create_record, update_record, note, prune],
        history_processors=[
            context_pressure_injector,
            notes_state_injector,
            prune_history_processor,
        ],
        retries=5,
        output_retries=2,
    )


def run_extraction(
    *,
    context_db_path: Path,
    project_identity: ProjectIdentity,
    session_id: str,
    trace_path: Path,
    model: Model,
    run_folder: Path,
    return_messages: bool = False,
):
    """Run the extract agent on one trace."""
    agent = build_extract_agent(model)
    deps = ContextDeps(
        context_db_path=context_db_path,
        project_identity=project_identity,
        session_id=session_id,
        trace_path=trace_path,
        run_folder=run_folder,
    )
    result = agent.run_sync(
        (
            "Read the trace, write exactly one episode record, and write only the strongest "
            "durable records with non-empty title and body."
        ),
        deps=deps,
        usage_limits=UsageLimits(request_limit=compute_request_budget(trace_path)),
    )
    if return_messages:
        return result.output, list(result.all_messages())
    return result.output


if __name__ == "__main__":
    """Run a tiny constructor smoke check."""
    assert SYSTEM_PROMPT
    print("extract agent: self-test passed")
