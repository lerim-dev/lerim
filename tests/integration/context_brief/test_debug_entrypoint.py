"""Real-LLM integration coverage for the Context Brief agent."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.integration.common_helpers import (
    retry_on_overload,
    seed_session,
    store_and_identity,
)


@pytest.mark.integration
@pytest.mark.llm
@pytest.mark.agent
def test_context_brief_agent_real_llm_generates_current_artifact(
    live_config,
    live_repo_root,
    live_runtime,
) -> None:
    """Context Brief should read seeded records, call the LLM, and write artifacts."""
    store, identity = store_and_identity(live_config, live_repo_root)
    seed_session_id = "integration-agent-context-brief-seed"
    seed_session(
        store,
        project_id=identity.project_id,
        session_id=seed_session_id,
        repo_root=live_repo_root,
        agent_type="integration-context-brief",
        source_trace_ref="context-brief-seed",
    )
    record = store.create_record(
        project_id=identity.project_id,
        session_id=seed_session_id,
        record_id="brief_refund_policy",
        kind="fact",
        title="Refund escalations require two evidence fields",
        body=(
            "Refund escalations over EUR 500 must include the customer-visible reason "
            "and the internal approval reference."
        ),
        change_reason="integration_seed",
    )

    result = retry_on_overload(
        lambda: live_runtime.context_brief(
            repo_root=live_repo_root,
            project_name="live-project",
            force=True,
            trigger="integration-agent-test",
        )
    )

    current_file = Path(str(result["current_file"]))
    run_file = Path(str(result["run_folder"])) / "CONTEXT_BRIEF.md"
    assert result["status"] == "generated"
    assert result["records_considered"] >= 1
    assert current_file.is_file()
    assert run_file.is_file()
    assert str(record["record_id"]) in current_file.read_text(encoding="utf-8")
