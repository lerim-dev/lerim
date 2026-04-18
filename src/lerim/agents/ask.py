"""Ask agent for Lerim's DB-only context system."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from datetime import datetime, timezone

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models import Model
from pydantic_ai.usage import UsageLimits

from lerim.agents.tools import ContextDeps, context_query, fetch_records, list_records, search_records
from lerim.context.project_identity import ProjectIdentity


def format_ask_hints(hits: list[dict[str, Any]], context_docs: list[dict[str, Any]]) -> str:
    """Format optional hints into a compact prompt preface."""
    del context_docs
    if not hits:
        return "(no pre-fetched hints)"
    lines = []
    for hit in hits:
        lines.append(
            f"- [{hit.get('kind', '?')}] {hit.get('title', '?')}: {hit.get('body_preview', '')}"
        )
    return "\n".join(lines)


ASK_SYSTEM_PROMPT = """\
You are the Lerim ask agent.

Answer questions from retrieved context records.

Use:
- `context_query` for deterministic count/list/date/latest questions
- `list_records` to browse recent or filtered records by exact fields like time, kind, and status
- `search_records` to retrieve candidate records for semantic questions
- `fetch_records` to inspect the best candidates

Rules:
- answer from retrieved records only
- distinguish current truth from historical truth
- say clearly when support is only episodic
- keep the answer concise and evidence-backed
- treat "learning" as a durable non-episode record unless the user says otherwise
- when the question asks for latest/last/recent/yesterday/by date, prefer exact record listing/querying before synthesis
- for mixed questions, first narrow with `list_records` or `context_query`, then `fetch_records`, then answer

Tool strategy:
- For "how many", use `context_query(mode="count")`.
- For "last", "latest", or "recent", use `list_records(order_by=...)` or `context_query(mode="list", order_by=...)`.
- For time windows like "yesterday" or "this week", use exact date filters first, then fetch the records you need.
- For "why", "what do we know", or topic questions, use `search_records`, then `fetch_records`.
- For mixed questions like "main learnings from yesterday", first narrow by time with `list_records` or `context_query`, then fetch the best records, then answer.
"""


class AskResult(BaseModel):
    """Structured output for the ask flow."""

    answer: str = Field(description="Answer text with record citations when available")


def build_ask_agent(model: Model) -> Agent[ContextDeps, AskResult]:
    """Build the ask agent with read-only DB tools."""
    return Agent(
        model,
        deps_type=ContextDeps,
        output_type=AskResult,
        system_prompt=ASK_SYSTEM_PROMPT,
        tools=[context_query, list_records, search_records, fetch_records],
        retries=5,
        output_retries=2,
    )


def run_ask(
    *,
    context_db_path: Path,
    project_identity: ProjectIdentity,
    project_ids: list[str],
    session_id: str,
    model: Model,
    question: str,
    hints: str = "",
    request_limit: int = 30,
    return_messages: bool = False,
):
    """Run the ask agent over the selected project scopes."""
    agent = build_ask_agent(model)
    deps = ContextDeps(
        context_db_path=context_db_path,
        project_identity=project_identity,
        session_id=session_id,
        project_ids=project_ids,
    )
    now_utc = datetime.now(timezone.utc).isoformat()
    prompt = (
        f"Current UTC time:\n{now_utc}\n\n"
        f"Question:\n{question.strip()}\n\n"
        f"Hints:\n{hints.strip() or '(no hints)'}"
    )
    result = agent.run_sync(
        prompt,
        deps=deps,
        usage_limits=UsageLimits(request_limit=max(1, int(request_limit))),
    )
    if return_messages:
        return result.output, list(result.all_messages())
    return result.output


if __name__ == "__main__":
    """Run a tiny constructor smoke check."""
    assert ASK_SYSTEM_PROMPT
    print("ask agent: self-test passed")
