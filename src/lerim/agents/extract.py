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
    context_apply,
    context_fetch,
    context_pressure_injector,
    context_search,
    note,
    notes_state_injector,
    prune,
    prune_history_processor,
    trace_read,
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
- Use `context_search` before creating a durable record if you suspect a similar record may already exist.
- Use `context_fetch` only for the few records you may update or supersede.
- Use `context_apply` for all durable writes.

Required flow:

1. Read the full trace with `trace_read`.
2. Use `note` throughout to preserve durable evidence and session themes.
3. Create exactly one `episode` record.
4. Create or update only a small number of durable records.
5. Prefer fewer, higher-quality records over many local facts.

Efficiency rules:

- For traces that fit in one `trace_read`, do not read them again.
- Use `note` in batches, not one finding per tool call.
- Search only when you are about to create or update a durable record.
- Stop as soon as the episode and the strongest durable records are written.
- Usually you should finish in a handful of tool calls, not dozens.

Decision records must include:
- `decision`
- `why`
- optional `alternatives`
- optional `consequences`

Episode records must include:
- `user_intent`
- `what_happened`
- optional `outcomes`

Do not talk about filenames, index documents, folder layouts, or archive paths.
You are editing meaning, not storage mechanics.
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
        tools=[trace_read, context_search, context_fetch, context_apply, note, prune],
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
            "Read the trace, write one episode record, and write durable records only "
            "for the strongest durable themes."
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
