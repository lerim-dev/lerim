"""Maintain agent for Lerim's DB-only context system."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models import Model
from pydantic_ai.usage import UsageLimits

from lerim.agents.tools import ContextDeps, context_apply, context_fetch, context_search
from lerim.context.project_identity import ProjectIdentity


MAINTAIN_SYSTEM_PROMPT = """\
You are the Lerim maintain agent.

Your job is to keep the context store healthy over time.

You may:
- update records when the same meaning becomes clearer
- archive records when they are no longer active truth
- supersede old truth with new truth
- add links between related records

You should prefer:
- fewer, cleaner records
- explicit supersession over silent overwrite
- evidence-backed updates

You should not:
- browse files
- talk about storage layout
- invent storage mechanics

Use:
- `context_search` to find candidate records
- `context_fetch` to inspect only the records you may change
- `context_apply` to perform one semantic mutation at a time
"""


class MaintainResult(BaseModel):
    """Structured output for the maintain flow."""

    completion_summary: str = Field(description="Short plain-text completion summary")


def build_maintain_agent(model: Model) -> Agent[ContextDeps, MaintainResult]:
    """Build the maintain agent with DB tools."""
    return Agent(
        model,
        deps_type=ContextDeps,
        output_type=MaintainResult,
        system_prompt=MAINTAIN_SYSTEM_PROMPT,
        tools=[context_search, context_fetch, context_apply],
        retries=5,
        output_retries=2,
    )


def run_maintain(
    *,
    context_db_path: Path,
    project_identity: ProjectIdentity,
    session_id: str,
    model: Model,
    request_limit: int = 30,
    return_messages: bool = False,
):
    """Run the maintain agent for one project scope."""
    agent = build_maintain_agent(model)
    deps = ContextDeps(
        context_db_path=context_db_path,
        project_identity=project_identity,
        session_id=session_id,
    )
    result = agent.run_sync(
        "Review the active records and improve the store with only semantic DB mutations.",
        deps=deps,
        usage_limits=UsageLimits(request_limit=max(1, int(request_limit))),
    )
    if return_messages:
        return result.output, list(result.all_messages())
    return result.output


if __name__ == "__main__":
    """Run a tiny constructor smoke check."""
    assert MAINTAIN_SYSTEM_PROMPT
    print("maintain agent: self-test passed")
