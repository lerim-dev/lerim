"""Real-LLM integration coverage for the context-answerer agent."""

from __future__ import annotations

import json

import pytest

from lerim.agents.context_answerer import run_context_answerer
from tests.integration.common_helpers import (
    retry_on_overload,
    seed_session,
    store_and_identity,
)


@pytest.mark.integration
@pytest.mark.llm
@pytest.mark.agent
def test_context_answerer_agent_real_llm_answers_from_seeded_context(
    live_config,
    live_repo_root,
) -> None:
    """Context answerer should plan retrieval and synthesize from returned records."""
    store, identity = store_and_identity(live_config, live_repo_root)
    seed_session_id = "integration-agent-answerer-seed"
    seed_session(
        store,
        project_id=identity.project_id,
        session_id=seed_session_id,
        repo_root=live_repo_root,
        agent_type="integration-context-answerer",
        source_trace_ref="context-answerer-seed",
    )
    record = store.create_record(
        project_id=identity.project_id,
        session_id=seed_session_id,
        record_id="answerer_refund_policy",
        kind="fact",
        title="Refund escalations require two evidence fields",
        body=(
            "Refund escalations over EUR 500 must include the customer-visible reason "
            "and the internal approval reference."
        ),
        change_reason="integration_seed",
    )

    result, events = retry_on_overload(
        lambda: run_context_answerer(
            context_db_path=live_config.context_db_path,
            project_identity=identity,
            project_ids=[identity.project_id],
            session_id="integration-agent-context-answerer",
            question="What evidence is required for refund escalations over EUR 500?",
            config=live_config,
            return_messages=True,
        )
    )

    functions = [str(event.get("function") or "") for event in events]
    retrievals = [event for event in events if event.get("kind") == "retrieval"]
    answer = result.answer.lower()
    assert "PlanContextRetrieval" in functions
    assert "AnswerFromContext" in functions
    assert retrievals
    assert "customer" in answer
    assert "approval" in answer
    assert str(record["record_id"]) in json.dumps(events, ensure_ascii=True)
