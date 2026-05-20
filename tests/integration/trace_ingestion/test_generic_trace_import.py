"""Real-LLM integration coverage for explicit generic trace imports."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lerim.traces.importer import import_trace_file
from tests.integration.common_helpers import retry_on_overload
from tests.live_helpers import (
    assert_clean_context_schema,
    assert_quality_metrics,
    audit_context_db,
    connect_context_db,
)


@pytest.mark.integration
@pytest.mark.llm
@pytest.mark.agent
def test_generic_trace_import_no_durable_signal_creates_only_archived_episode(
    live_config,
    live_repo_root: Path,
) -> None:
    """Generic imports should use the real extraction path and abstain on low-signal traces."""
    trace_path = live_repo_root / "routine-support-followup.jsonl"
    session_id = "integration-generic-import-no-durable"
    trace_path.write_text(
        "\n".join(
            json.dumps(item, ensure_ascii=True)
            for item in [
                {
                    "role": "user",
                    "content": (
                        "Close the support follow-up after confirming the customer "
                        "received the already-approved renewal notice."
                    ),
                    "timestamp": "2026-05-20T10:00:00Z",
                },
                {
                    "role": "assistant",
                    "content": (
                        "I confirmed the notice was received, marked the one-off "
                        "follow-up complete, and did not identify any reusable policy "
                        "or process change."
                    ),
                    "timestamp": "2026-05-20T10:04:00Z",
                },
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = retry_on_overload(
        lambda: import_trace_file(
            trace_path=trace_path,
            source_name="support-agent",
            source_profile="support",
            scope_type="project",
            scope=str(live_repo_root),
            session_id=session_id,
            config=live_config,
        )
    )

    assert result.session_id == session_id
    assert result.ingest_result["records_created"] == 1
    assert result.ingest_result["scope_type"] == "project"
    assert result.normalized_trace_path.is_file()

    with connect_context_db(live_config.context_db_path) as conn:
        rows = conn.execute(
            """
            SELECT kind, status, source_name, source_profile
            FROM records
            WHERE source_session_id = ?
            ORDER BY created_at
            """,
            (session_id,),
        ).fetchall()
        active_count = int(
            conn.execute(
                "SELECT COUNT(*) FROM records WHERE status = 'active'"
            ).fetchone()[0]
        )

    assert len(rows) == 1
    assert rows[0]["kind"] == "episode"
    assert rows[0]["status"] == "archived"
    assert rows[0]["source_name"] == "support-agent"
    assert rows[0]["source_profile"] == "support"
    assert active_count == 0
    assert_clean_context_schema(live_config.context_db_path)
    assert_quality_metrics(audit_context_db(live_config.context_db_path))
