"""Real-LLM integration coverage for the context-graph agent."""

from __future__ import annotations

import pytest

from lerim.agents.context_graph import run_context_graph
from tests.integration.common_helpers import (
    retry_on_overload,
    seed_session,
    store_and_identity,
)


@pytest.mark.integration
@pytest.mark.llm
@pytest.mark.agent
def test_context_graph_agent_real_llm_links_seeded_records(
    live_config,
    live_repo_root,
) -> None:
    """Context graph should link related seeded records and persist graph rows."""
    store, identity = store_and_identity(live_config, live_repo_root)
    seed_session_id = "integration-agent-context-graph-seed"
    session_id = "integration-agent-context-graph"
    seed_session(
        store,
        project_id=identity.project_id,
        session_id=seed_session_id,
        repo_root=live_repo_root,
        agent_type="integration-context-graph",
        source_trace_ref="context-graph-seed",
    )
    seed_session(
        store,
        project_id=identity.project_id,
        session_id=session_id,
        repo_root=live_repo_root,
        agent_type="integration-context-graph",
        source_trace_ref="context-graph-run",
    )
    store.create_record(
        project_id=identity.project_id,
        session_id=seed_session_id,
        record_id="graph_refund_approval_decision",
        kind="decision",
        title="Use approval workflow for high-value refunds",
        body="Refund escalations over EUR 500 require supervisor approval before customer commitment.",
        decision="Use supervisor approval for high-value refunds.",
        why="Large refunds need accountable approval before support promises an outcome.",
        change_reason="integration_seed",
    )
    store.create_record(
        project_id=identity.project_id,
        session_id=seed_session_id,
        record_id="graph_refund_policy_evidence",
        kind="fact",
        title="High-value refund policy threshold",
        body="Billing policy evidence states that refunds above EUR 500 require supervisor approval.",
        change_reason="integration_seed",
    )

    result, details = retry_on_overload(
        lambda: run_context_graph(
            context_db_path=live_config.context_db_path,
            project_identity=identity,
            session_id=session_id,
            config=live_config,
            max_llm_calls=4,
            return_details=True,
        )
    )

    actions = [event.action for event in details.events]
    assert result.completion_summary.strip()
    assert details.llm_calls >= 1
    assert result.nodes_written >= 2
    assert result.edges_written >= 1
    for expected in (
        "load_inventory",
        "build_semantic_candidates",
        "link_records",
        "review_links",
        "persist_context_graph",
        "final_result",
    ):
        assert expected in actions
