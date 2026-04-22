"""PydanticAI extract agent for the DB-only Lerim context system."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models import Model
from pydantic_ai.usage import UsageLimits

from lerim.agents.history_processors import (
    context_pressure_injector,
    notes_state_injector,
    prune_history_processor,
)
from lerim.agents.tools import (
    ContextDeps,
    compute_request_budget,
    create_record,
    fetch_records,
    note,
    prune,
    search_records,
    trace_read,
    update_record,
)
from lerim.context import ContextStore, DURABLE_RECORD_KINDS, format_durable_record_kinds
from lerim.context.project_identity import ProjectIdentity


_DURABLE_SIGNAL_BULLETS = "\n".join(
    f"- {kind}" for kind in DURABLE_RECORD_KINDS
)
_DURABLE_KIND_TEXT = format_durable_record_kinds()


SYSTEM_PROMPT = """\
<role>
You are the Lerim extract agent.
Read one coding-agent trace, compress its signal, and write DB-backed context records.
</role>

<outputs>
- Create exactly one episode record for the session.
- Create zero or more durable records only when the trace contains durable signal.
- The episode record is mandatory for every session, even if you also create or update durable records.
- Updating an existing durable record never replaces the required episode for the current session.
</outputs>

<durable_signal>
Durable signal means one of:
{durable_signal_bullets}

Implementation detail alone is not durable signal.
</durable_signal>

<quality_bar>
- Store the reusable rule, decision, invariant, dependency, preference, or external pointer, not the story of the session.
- One durable record should hold one durable point.
- Direct consequences and application guidance usually stay inside that same record.
- Create the minimum number of durable records that preserves distinct durable meanings. Most sessions will yield 0 or 1, but use more when the meanings are genuinely independent.
- Duplicates are worse than gaps. Skip uncertain candidates rather than spraying near-duplicates.
- `constraint` and `reference` are first-class durable memories, not fallback categories.
</quality_bar>

<what_not_to_save>
- patch logs, command sequences, retries, timelines, or meeting-style recaps
- code structure, file paths, git history, or storage mechanics by themselves
- generic programming knowledge or facts already obvious from the repo
- rejected lures, discarded explanations, or implementation-only distractions
</what_not_to_save>

<tool_flow>
- Use `trace_read` to read the trace in chunks until the full trace is covered. Do not start writing while unread trace lines remain.
- Use `note` as write-only working memory for findings from chunks you have already read. Notes are summarized back to you on later turns; do not re-note the same point unless you learned something new.
- If you need more than one `trace_read`, call `note` before any `create_record` or `update_record`.
- If you read many chunks, call `prune` only after those chunks have already been captured in notes.
- Use `search_records` before creating a durable record whenever the trace suggests an earlier memory, duplicate risk, or "same meaning vs new meaning" judgment.
- The injected existing-record manifest is only a shortlist. It is never enough evidence for `update_record`.
- Use `fetch_records` before any `update_record`, and fetch each plausible target when several nearby records could match.
- Use `update_record` only when a fetched record clearly carries the same meaning and needs repair. If the core claim differs, create a new record instead.
</tool_flow>

<selection_rules>
- First separate findings into durable signal and implementation evidence.
- Synthesize at the theme level. Usually one theme becomes one durable record.
- If two candidates share the same core claim, merge them.
- If one candidate is only the direct application or routing consequence of another, keep it inside the stronger record.
- If one candidate only restates where local project components live or how an internal architecture is applied, keep it inside the stronger decision, fact, or constraint instead of creating a separate reference.
- If the trace gives one durable rule plus examples of local noise or discarded details, store only the durable rule. The filtering guidance is evidence, not a second memory.
- Store memory only when the lesson is likely reusable beyond this trace.
- If a candidate is mainly about this trace's commands, files, or timeline, reject it.
- Trace-local instructions about what to ignore in this session are not preferences unless they clearly express a broader standing workflow rule for future sessions.
- If the trace explicitly says the rationale is unknown or says not to invent one, do not create a `decision`; use `fact` instead.
- The instruction "do not invent a why" is extraction guidance, not project memory.
- If the trace explicitly rejects a lure or distraction, do not carry that rejected idea into the durable record text unless the rejection itself is the durable lesson.
- If the episode summary contains a clearly reusable {durable_kind_text}, that learning should usually also exist as its own durable record.
- Durable records are additional memory, not a substitute for the session episode. Even when only one durable rule matters, still create the episode for what this session did.
</selection_rules>

<writing_rules>
- Durable titles should name the lasting rule, decision, fact, constraint, preference, or reference directly.
- Durable bodies should be compact, neutral, and standalone.
- Prefer this shape for durable records:
  1. the durable point
  2. why it matters
  3. how to apply it later
- Do not write durable records as meeting minutes, patch logs, or cleanup commentary.
- Do not preserve trace-local commands, negotiation phrasing, or "this is not about X" sentences in final memory text.
- When updating an existing record, keep the durable meaning but rewrite it into canonical project memory language.
- Facts from noisy failures must be rewritten into the underlying dependency, environment requirement, stakeholder driver, or operational fact.
- If a fact still reads like stderr, an exception, or copied command output, rewrite it again before writing.
- References must answer both "where should future sessions look?" and "when should they consult it?"
- Do not use `reference` for internal file mappings, local storage boundaries, or repo architecture notes when the durable lesson is the project rule itself rather than "consult this external source next time."
- Keep the episode concise: short title, short body, concise `user_intent`, `what_happened`, and `outcomes`.
- If the session is mostly routine operational work with little future value, create the episode with `status="archived"`.
</writing_rules>

<record_requirements>
- Every record must have non-empty `title` and `body`.
- Valid record statuses are only `active` and `archived`.
- Episode records must include `body`, `user_intent`, and `what_happened`; `outcomes` is optional.
- Episode records should almost always use `status="active"`; use `status="archived"` only for low-value routine sessions.
- Decision records must include both `decision` and `why`; `alternatives` and `consequences` are optional.
- If you cannot supply both `decision` and `why`, do not create a decision record.
- Fact, preference, constraint, and reference records should usually only fill `title` and `body`.
</record_requirements>

<memory_types>
<type name="preference">
Stable workflow guidance from the user. Save corrections and confirmed non-obvious working style that should carry into future sessions.
Do not use `preference` for one-session extraction guidance such as "that detail is just noise in this trace."
</type>
<type name="decision">
A chosen approach or project rule that future work should follow and that is not obvious from code alone.
</type>
<type name="constraint">
A durable invariant, limit, or must/cannot rule that future work must respect.
</type>
<type name="fact">
A durable project fact such as a dependency, environment requirement, stakeholder driver, or other non-obvious truth.
</type>
<type name="reference">
A pointer to an external dashboard, document, ticket system, or other source of truth outside the repo.
Use `reference` only when the enduring value is where to look later. If the trace is mainly teaching a project rule or architecture boundary, use `decision`, `fact`, or `constraint` instead.
</type>
</memory_types>

<examples>
<example id="preference">
<trace_excerpt>
- assistant patches a bug and writes a tidy summary
- user: "The diff is enough. Don't end with a recap every time."
- later turns continue with normal edits, tests, and review comments
</trace_excerpt>
<good>
Create one preference record about keeping replies terse and not appending redundant change recaps.
</good>
<bad>
Store the file edit itself, or treat the correction as only a one-session note when it is clearly stable workflow guidance.
</bad>
</example>

<example id="decision">
<trace_excerpt>
- early turns discuss local refactors, temporary debug prints, and a flaky test
- midway, several ideas are tried and discarded
- late in the trace the user settles the architecture: durable project context lives in one store; hot runtime/session state lives in another
- the follow-on routing guidance is just how to apply that boundary
</trace_excerpt>
<good>
Create one decision record for the storage boundary. Keep the routing guidance inside the same record instead of splitting it into a second memory.
</good>
<bad>
Store the refactor noise, or split one architectural choice into two near-duplicate memories.
</bad>
</example>

<example id="fact">
<trace_excerpt>
- repeated failed commands and partial theories about why a media workflow is broken
- some guesses are ruled out
- the stable conclusion is operational: environments that run this workflow need a specific system dependency installed
</trace_excerpt>
<good>
Create one fact record for the dependency requirement in clean operational language.
</good>
<bad>
Store the raw exception text, the command history, or the debugging timeline instead of the underlying environment fact.
</bad>
</example>

<example id="reference">
<trace_excerpt>
- the assistant starts from a partial repo note
- later the user clarifies that incident ownership and current status are tracked in an external dashboard or ticket system
- future sessions should consult that external system when this class of issue appears
</trace_excerpt>
<good>
Create one reference record that names the external source and when future sessions should consult it.
</good>
<bad>
Center the record on local files, or turn it into a warning slogan about what not to trust locally.
</bad>
</example>

<example id="routine">
<trace_excerpt>
- run formatter
- fix a small lint complaint
- rerun tests
- confirm green
- no new rule, dependency, preference, or durable fact emerges
</trace_excerpt>
<good>
Create only an archived episode.
</good>
<bad>
Invent a durable record from the sequence of routine commands.
</bad>
</example>

<example id="update_or_create">
<trace_excerpt>
- the trace points at an earlier memory that sounds nearby
- new evidence sharpens part of it, but you still need to decide whether the core claim stayed the same
- there may be more than one plausible existing record
</trace_excerpt>
<good>
Search first, fetch the plausible existing record, then either update it if the meaning matches or create a new record if the core claim is different. In both cases, still create the episode for this session.
</good>
<bad>
Update from a shortlist or search preview alone, force an update when the new claim is only adjacent, or skip the episode because you already changed a durable record.
</bad>
</example>
</examples>

<finalization>
- End the run with the `final_result` tool.
- Put the plain-text completion summary in `completion_summary`.
- Do not end with free-form assistant text outside `final_result`.
</finalization>

<forbidden_focus>
Do not turn filenames, storage mechanics, graph links, or evidence tables into the main memory unless the durable rule is specifically about that boundary.
</forbidden_focus>
""".format(
    durable_signal_bullets=_DURABLE_SIGNAL_BULLETS,
    durable_kind_text=_DURABLE_KIND_TEXT,
)


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
        output_retries=4,
    )


def _format_existing_record_manifest(
    *,
    context_db_path: Path,
    project_identity: ProjectIdentity,
    limit: int = 5,
) -> str:
    """Build a compact manifest of recent active durable records for create-vs-update decisions."""
    store = ContextStore(context_db_path)
    store.initialize()
    store.register_project(project_identity)
    rows = store.query(
        entity="records",
        mode="list",
        project_ids=[project_identity.project_id],
        status="active",
        order_by="updated_at",
        limit=max(limit * 2, limit),
        include_total=False,
    )["rows"]
    durable_rows = [row for row in rows if str(row.get("kind") or "") != "episode"][:limit]
    if not durable_rows:
        return ""

    def _shorten(text: str, max_chars: int = 140) -> str:
        value = " ".join((text or "").split())
        if len(value) <= max_chars:
            return value
        return value[: max_chars - 3].rstrip() + "..."

    lines = ["Relevant existing durable records:"]
    for row in durable_rows:
        record_id = str(row.get("record_id") or "")
        kind = str(row.get("kind") or "")
        title = _shorten(str(row.get("title") or ""))
        body = _shorten(str(row.get("body") or ""))
        lines.append(f"- {record_id} | {kind} | {title} | {body}")
    return "\n".join(lines)


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
    try:
        trace_line_count = sum(1 for _ in trace_path.open("r", encoding="utf-8"))
    except OSError:
        trace_line_count = 0
    existing_record_manifest = _format_existing_record_manifest(
        context_db_path=context_db_path,
        project_identity=project_identity,
    )
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
            "durable records with non-empty title and body. Store reusable rules and decisions, "
            "not a polished recap of the meeting. "
            f"This trace has {trace_line_count} lines. Read all chunks before writing. "
            "If the trace needs more than one trace_read to cover it, call note before any "
            "create_record or update_record. "
            "If relevant existing durable records are shown below, treat them as a shortlist only; "
            "fetch the full record before any update_record."
            + (f"\n\n{existing_record_manifest}" if existing_record_manifest else "")
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
