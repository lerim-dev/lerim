"""Real-LLM integration tests for extract, maintain, and semantic ask."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from lerim.agents.ask import run_ask
from lerim.config.providers import build_pydantic_model
from lerim.context import ContextStore, resolve_project_identity
from tests.conftest import TRACES_DIR
from tests.live_helpers import (
    ASK_TOOL_NAMES,
    EXTRACT_TOOL_NAMES,
    FRAMEWORK_TOOL_NAMES,
    MAINTAIN_TOOL_NAMES,
    assert_clean_context_schema,
    assert_no_legacy_tools,
    assert_quality_metrics,
    connect_context_db,
    audit_context_db,
    dump_messages,
    extract_tool_names,
    read_agent_trace_tool_names,
)


def _seed_session(
    store: ContextStore,
    *,
    project_id: str,
    session_id: str,
    repo_root: Path,
    agent_type: str = "seed",
) -> None:
    """Insert one session row used as provenance for seeded records."""
    store.upsert_session(
        project_id=project_id,
        session_id=session_id,
        agent_type=agent_type,
        source_trace_ref=f"seed:{session_id}",
        repo_path=str(repo_root),
        cwd=str(repo_root),
        started_at=datetime.now(timezone.utc).isoformat(),
        model_name="seed",
        instructions_text=None,
        prompt_text=None,
        metadata={},
    )


@pytest.mark.integration
@pytest.mark.llm
def test_live_extract_creates_good_records_and_derived_rows(
    live_config,
    live_runtime,
) -> None:
    """A real extract run should fill canonical rows, versions, embeddings, and FTS."""
    payload = live_runtime.sync(
        TRACES_DIR / "mixed_decisions_learnings.jsonl",
        session_id="integration-live-extract",
        agent_type="integration",
    )

    tool_names = read_agent_trace_tool_names(Path(payload["run_folder"]) / "agent_trace.json")
    assert "trace_read" in tool_names
    assert "note" in tool_names
    assert "create_record" in tool_names
    assert set(tool_names).issubset(EXTRACT_TOOL_NAMES | FRAMEWORK_TOOL_NAMES)
    assert_no_legacy_tools(tool_names)

    store = ContextStore(live_config.context_db_path)
    rows = store.query(
        entity="records",
        mode="list",
        project_ids=[payload["project_id"]],
        source_session_id="integration-live-extract",
        order_by="created_at",
        limit=20,
    )["rows"]
    record_ids = [str(row["record_id"]) for row in rows]
    assert len([row for row in rows if row["kind"] == "episode"]) == 1
    assert len([row for row in rows if row["kind"] != "episode"]) >= 1

    with connect_context_db(live_config.context_db_path) as conn:
        placeholders = ", ".join("?" for _ in record_ids)
        embedding_count = int(
            conn.execute(
                f"SELECT COUNT(*) FROM record_embeddings WHERE record_id IN ({placeholders})",
                tuple(record_ids),
            ).fetchone()[0]
        )
        fts_count = int(
            conn.execute(
                f"SELECT COUNT(*) FROM records_fts WHERE record_id IN ({placeholders})",
                tuple(record_ids),
            ).fetchone()[0]
        )
        version_count = int(
            conn.execute(
                f"SELECT COUNT(*) FROM record_versions WHERE record_id IN ({placeholders})",
                tuple(record_ids),
            ).fetchone()[0]
        )

    assert embedding_count == len(record_ids)
    assert fts_count == len(record_ids)
    assert version_count >= len(record_ids)

    assert_clean_context_schema(live_config.context_db_path)
    assert_quality_metrics(audit_context_db(live_config.context_db_path))


@pytest.mark.integration
@pytest.mark.llm
def test_live_maintain_preserves_fresh_decisions_and_cleans_low_value_rows(
    live_config,
    live_repo_root,
    live_runtime,
) -> None:
    """A real maintain run should avoid harmful archive behavior and fix obvious junk."""
    identity = resolve_project_identity(live_repo_root)
    store = ContextStore(live_config.context_db_path)
    store.initialize()
    store.register_project(identity)
    _seed_session(
        store,
        project_id=identity.project_id,
        session_id="seed-source-session",
        repo_root=live_repo_root,
    )
    decision_record = store.create_record(
        project_id=identity.project_id,
        session_id="seed-source-session",
        kind="decision",
        title="Use one global context DB",
        body="Durable context should live in one global SQLite database under ~/.lerim.",
        decision="Use one global context DB",
        why="One canonical store keeps durable context separate from session indexing and queue state.",
    )
    weak_fact = store.create_record(
        project_id=identity.project_id,
        session_id="seed-source-session",
        kind="fact",
        title="Placeholder duplicate note",
        body="Temporary duplicate note about the same global context DB decision.",
    )
    episode_record = store.create_record(
        project_id=identity.project_id,
        session_id="seed-source-session",
        kind="episode",
        title="Routine local sync",
        body="Routine sync. No durable learning.",
        user_intent="Run a routine local sync.",
        what_happened="The system synced local files and confirmed everything was up to date.",
        outcomes="No lasting decision or learning.",
    )

    payload = live_runtime.maintain(repo_root=live_repo_root, session_id="integration-maintain")

    tool_names = read_agent_trace_tool_names(Path(payload["run_folder"]) / "agent_trace.json")
    assert "search_records" in tool_names
    assert "fetch_records" in tool_names
    assert set(tool_names).issubset(MAINTAIN_TOOL_NAMES | FRAMEWORK_TOOL_NAMES)
    assert any(name in tool_names for name in ("archive_record", "supersede_record", "update_record"))
    assert_no_legacy_tools(tool_names)

    decision_after = store.fetch_record(
        decision_record["record_id"],
        project_ids=[identity.project_id],
        include_versions=True,
    )
    weak_fact_after = store.fetch_record(
        weak_fact["record_id"],
        project_ids=[identity.project_id],
        include_versions=True,
    )
    episode_after = store.fetch_record(
        episode_record["record_id"],
        project_ids=[identity.project_id],
        include_versions=True,
    )

    assert decision_after is not None
    assert decision_after["status"] == "active"
    assert weak_fact_after is not None
    assert episode_after is not None
    assert payload["records_updated"] + payload["records_archived"] >= 1
    assert episode_after["status"] == "archived"
    assert episode_after["valid_until"]

    assert_clean_context_schema(live_config.context_db_path)
    assert_quality_metrics(audit_context_db(live_config.context_db_path))


@pytest.mark.integration
@pytest.mark.llm
def test_live_ask_semantic_question_uses_search_and_fetch(
    live_config,
    live_repo_root,
) -> None:
    """A real ask run should retrieve supporting records with the DB-era read tools."""
    identity = resolve_project_identity(live_repo_root)
    store = ContextStore(live_config.context_db_path)
    store.initialize()
    store.register_project(identity)
    _seed_session(
        store,
        project_id=identity.project_id,
        session_id="ask-source-session",
        repo_root=live_repo_root,
    )
    store.create_record(
        project_id=identity.project_id,
        session_id="ask-source-session",
        kind="decision",
        title="Keep context and session databases separate",
        body=(
            "Use one SQLite database for durable context records and a second SQLite "
            "database for session indexing and queue operations."
        ),
        decision="Keep two SQLite databases",
        why="The durable context store and the hot session/queue catalog have different responsibilities and write patterns.",
        consequences="Context stays canonical while the index database stays operational.",
    )

    model = build_pydantic_model("agent", config=live_config)
    result, messages = run_ask(
        context_db_path=live_config.context_db_path,
        project_identity=identity,
        project_ids=[identity.project_id],
        session_id="integration-ask",
        model=model,
        question="Why do we keep two SQLite databases instead of one?",
        return_messages=True,
    )

    answer = result.answer.lower()
    assert "could not find" not in answer
    assert (
        "two sqlite" in answer
        or "two database" in answer
        or "two separate sqlite" in answer
    )
    assert "session" in answer or "queue" in answer or "index" in answer

    tool_names = extract_tool_names(dump_messages(messages))
    assert "search_records" in tool_names
    assert "fetch_records" in tool_names
    assert set(tool_names).issubset(ASK_TOOL_NAMES | FRAMEWORK_TOOL_NAMES)
    assert_no_legacy_tools(tool_names)
