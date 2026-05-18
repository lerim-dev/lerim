"""Real-LLM integration coverage for the trace-ingestion agent."""

from __future__ import annotations

import json

import pytest

from lerim.agents.trace_ingestion import run_trace_ingestion
from tests.integration.common_helpers import (
    retry_on_overload,
    seed_session,
    store_and_identity,
)


@pytest.mark.integration
@pytest.mark.llm
@pytest.mark.agent
def test_trace_ingestion_agent_real_llm_writes_scoped_context(
    live_config,
    live_repo_root,
) -> None:
    """Trace ingestion should resolve scope, filter signal, and persist records."""
    store, identity = store_and_identity(live_config, live_repo_root)
    session_id = "integration-agent-trace-ingestion"
    trace_path = live_repo_root / "support-agent-trace.jsonl"
    trace_path.write_text(
        "\n".join(
            json.dumps(item, ensure_ascii=True)
            for item in [
                {
                    "role": "user",
                    "content": (
                        "Review this support-agent handoff. Keep durable context only. "
                        "The durable policy is that refund escalations over EUR 500 must include "
                        "the customer-visible reason and the internal approval reference."
                    ),
                },
                {
                    "role": "assistant",
                    "content": (
                        "I checked the billing workflow. Temporary ticket labels, local notes, "
                        "and draft wording are not reusable. The durable context is the refund "
                        "escalation policy and its required evidence fields."
                    ),
                },
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    seed_session(
        store,
        project_id=identity.project_id,
        session_id=session_id,
        repo_root=live_repo_root,
        agent_type="integration-trace-ingestion",
        source_trace_ref=str(trace_path),
    )

    result, details = retry_on_overload(
        lambda: run_trace_ingestion(
            context_db_path=live_config.context_db_path,
            project_identity=identity,
            session_id=session_id,
            trace_path=trace_path,
            config=live_config,
            session_started_at="2026-05-15T00:00:00+00:00",
            source_name="support-agent",
            source_profile="support",
            max_llm_calls=5,
            return_details=True,
        )
    )

    actions = [event.action for event in details.events]
    assert result.completion_summary.strip()
    for expected in (
        "resolve_scope",
        "read_window",
        "scan_window",
        "filter_signals",
        "synthesize_records",
        "save_context",
    ):
        assert expected in actions
    assert details.scope_type == "project"
    rows = store.query(
        entity="records",
        mode="list",
        project_ids=[identity.project_id],
        source_session_id=session_id,
        order_by="created_at",
        limit=10,
        include_archived=True,
    )["rows"]
    assert any(row["kind"] == "episode" for row in rows)
    assert any(row["kind"] != "episode" for row in rows)
