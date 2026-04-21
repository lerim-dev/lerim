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
- when the question asks what is true now versus before, explicitly label which record-backed claim is current and which is historical
- if support is only episodic, say explicitly: "support is only episodic; no durable record was found"
- if both durable and episodic support exist, use the durable record as primary support and treat the episode as secondary context
- keep the answer concise and evidence-backed
- treat "learning" as a durable non-episode record unless the user says otherwise
- when the question asks for latest/last/recent/yesterday/by date, prefer exact record listing/querying before synthesis
- when an exact list/query already identifies the answer, do not add semantic search
- for mixed questions, first narrow with `list_records` or `context_query`, then `fetch_records`, then answer
- Durable record kinds include `decision`, `fact`, `constraint`, `preference`, and `reference`.

Tool strategy:
- For "how many" questions about records, memories, or learnings, use `context_query(entity="records", mode="count")`.
- For "last", "latest", or "recent", use `list_records(order_by=...)` or `context_query(mode="list", order_by=...)`.
- For exact latest questions about a known kind, use `list_records(kind_filters=[...], order_by=...)` with the matching kind name.
- For questions like "latest decision", "latest fact", "latest constraint", "latest preference", or "latest reference", always set `kind_filters` to that exact durable kind name before you answer.
- Do not answer a latest-by-kind question from a latest-overall listing. If the question asks for a kind, the exact listing must also filter to that kind.
- If an exact latest-by-kind listing returns a row of the wrong kind, correct the filter and retry exact listing. Do not switch to semantic search for that question.
- Valid `order_by` values are exactly `created_at`, `updated_at`, and `valid_from`.
- Do not write `desc`, `asc`, or SQL-like order strings in `order_by`. Pass only the bare field name and rely on the tool's built-in ordering.
- For exact "latest", "last", count, and date-window questions, do not use `search_records` unless the question also asks about a topic that exact listing cannot identify on its own.
- For time windows like "yesterday" or "this week", use exact date filters first, then fetch the records you need.
- For "as of", "on DATE", "at that time", or other truth-at-time questions, use `valid_at` in the exact retrieval step instead of answering from latest truth.
- For time-window questions that also name a kind, combine both constraints in the exact step. Example: "What decisions were made yesterday?" should narrow by time and `kind_filters=["decision"]` before synthesis.
- Do not answer a time-window question from a partial exact listing that misses the named kind or the requested date window. Correct the exact filters and retry first.
- For mixed time-plus-topic questions like "What changed yesterday around vector search?", first narrow the time window with `list_records` or `context_query`.
- After the exact time narrowing step, you may use `fetch_records` directly if the narrowed set is already small and clearly relevant, or use `search_records` only as a second step to refine within the time-bounded set.
- Do not start a mixed time-plus-topic question with `search_records`. The first retrieval step must be exact time narrowing.
- For "now vs before", "current vs historical", or "used to", retrieve both the current support and the historical support before answering.
- Preferred workflow for current-vs-historical questions:
  1. use `list_records(include_archived=true, ...)` when exact filtering is enough, or `context_query(entity="records", mode="list", ...)` because that list mode already includes archived rows
  2. then `fetch_records` for the current and historical records you will cite
- If you use `list_records` or `search_records` for a current-vs-historical question, set `include_archived=true`.
- Do not pass `include_archived` to `context_query`; that tool does not take it.
- Do not use semantic search for a current-vs-historical question when an exact record listing already gives both the current row and the historical row.
- Do not answer a current-versus-historical question from current rows only.
- For exact query questions, you may answer directly without `fetch_records` only when the query already covers every record needed for the answer.
- For "why", "what do we know", or topic questions, use `search_records`, then `fetch_records`.
- Semantic neighbors are not support. If retrieved rows are only adjacent in wording or technology and do not directly answer the question, say so instead of stretching them into a positive claim.
- For mixed questions like "main learnings from yesterday", first narrow by time with `list_records` or `context_query`, then fetch the best records, then answer.
- Valid `context_query` entities are `records`, `memories`, `learnings`, `versions`, and `sessions`. Do not invent entity names like `current` or `project`.
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
