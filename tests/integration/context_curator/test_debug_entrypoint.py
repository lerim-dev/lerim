"""Real-LLM integration coverage for the context-curator agent."""

from __future__ import annotations

import pytest

from lerim.agents.context_curator import run_context_curator
from tests.integration.common_helpers import (
    retry_on_overload,
    seed_session,
    store_and_identity,
)


@pytest.mark.integration
@pytest.mark.llm
@pytest.mark.agent
def test_context_curator_agent_real_llm_reviews_seeded_records(
    live_config,
    live_repo_root,
) -> None:
    """Context curator should inventory, review, and finish on real model output."""
    store, identity = store_and_identity(live_config, live_repo_root)
    seed_session_id = "integration-agent-curator-seed"
    session_id = "integration-agent-context-curator"
    seed_session(
        store,
        project_id=identity.project_id,
        session_id=seed_session_id,
        repo_root=live_repo_root,
        agent_type="integration-context-curator",
        source_trace_ref="context-curator-seed",
    )
    seed_session(
        store,
        project_id=identity.project_id,
        session_id=session_id,
        repo_root=live_repo_root,
        agent_type="integration-context-curator",
        source_trace_ref="context-curator-run",
    )
    for record_id, title, body in (
        (
            "curator_refund_policy_weak",
            "Refund escalation policy",
            "Refund escalations over EUR 500 need customer reason and approval reference.",
        ),
        (
            "curator_refund_policy_strong",
            "Refund escalations over EUR 500 need evidence fields",
            "Refund escalations over EUR 500 must include the customer-visible reason and internal approval reference.",
        ),
    ):
        store.create_record(
            project_id=identity.project_id,
            session_id=seed_session_id,
            record_id=record_id,
            kind="fact",
            title=title,
            body=body,
            change_reason="integration_seed",
        )

    result, details = retry_on_overload(
        lambda: run_context_curator(
            context_db_path=live_config.context_db_path,
            project_identity=identity,
            session_id=session_id,
            config=live_config,
            max_llm_calls=6,
            return_details=True,
        )
    )

    actions = [event.action for event in details.events]
    assert result.completion_summary.strip()
    assert "load_inventory" in actions
    assert "build_similarity_clusters" in actions
    assert "final_result" in actions
    assert any(
        action in actions for action in ("review_cluster", "review_health_batch")
    )
