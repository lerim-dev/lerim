"""Live smoke checks for the real extract agent and DB write path."""

from __future__ import annotations

from pathlib import Path

import pytest

from lerim.context.store import ContextStore
from tests.conftest import TRACES_DIR
from tests.live_helpers import (
    EXTRACT_TOOL_NAMES,
    FRAMEWORK_TOOL_NAMES,
    assert_clean_context_schema,
    assert_no_legacy_tools,
    assert_quality_metrics,
    audit_context_db,
    read_agent_trace_tool_names,
)


@pytest.mark.smoke
@pytest.mark.llm
def test_live_extract_smoke_writes_records_and_uses_db_tools(
    live_config,
    live_runtime,
) -> None:
    """A tiny real-LLM extract run should write good records and use only DB-era tools."""
    trace_path = TRACES_DIR / "mixed_decisions_learnings.jsonl"
    session_id = "smoke-live-extract"

    payload = live_runtime.sync(trace_path, session_id=session_id, agent_type="smoke")

    agent_trace_path = Path(payload["run_folder"]) / "agent_trace.json"
    tool_names = read_agent_trace_tool_names(agent_trace_path)
    assert "trace_read" in tool_names
    assert "create_record" in tool_names
    assert set(tool_names).issubset(EXTRACT_TOOL_NAMES | FRAMEWORK_TOOL_NAMES)
    assert_no_legacy_tools(tool_names)

    store = ContextStore(live_config.context_db_path)
    rows = store.query(
        entity="records",
        mode="list",
        project_ids=[payload["project_id"]],
        source_session_id=session_id,
        order_by="created_at",
        limit=20,
        include_total=True,
    )["rows"]
    episode_rows = [row for row in rows if row["kind"] == "episode"]
    durable_rows = [row for row in rows if row["kind"] != "episode"]
    decision_rows = [row for row in rows if row["kind"] == "decision"]

    assert len(episode_rows) == 1
    assert len(durable_rows) >= 1
    assert len(decision_rows) >= 1

    assert_clean_context_schema(live_config.context_db_path)
    metrics = audit_context_db(live_config.context_db_path)
    assert_quality_metrics(metrics)
