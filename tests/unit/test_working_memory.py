"""Unit tests for generated Working Memory behavior."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from lerim.context import ContextStore, resolve_project_identity
from lerim.server.runtime import LerimRuntime
from lerim.working_memory import (
    MemoryLine,
    MemorySection,
    WorkingMemoryDraft,
    count_changed_records_since,
    load_candidate_records,
    render_working_memory_markdown,
    resolve_working_memory_project,
    working_memory_paths,
)
from tests.helpers import make_config, run_cli, run_cli_json, write_test_config


@pytest.fixture
def mock_embeddings(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Patch embeddings so context writes remain local and deterministic."""
    provider = MagicMock()
    provider.embedding_dims = 384
    provider.model_id = "test-model"
    provider.embed_document.return_value = [0.1] * 384
    provider.embed_query.return_value = [0.1] * 384
    monkeypatch.setattr("lerim.context.store.get_embedding_provider", lambda: provider)
    return provider


def _register_seeded_project(store: ContextStore, repo: Path) -> str:
    """Register a project plus one source session and return project_id."""
    identity = resolve_project_identity(repo)
    store.register_project(identity)
    store.upsert_session(
        project_id=identity.project_id,
        session_id="sess_working_memory",
        agent_type="test",
        source_trace_ref="trace.jsonl",
        repo_path=str(identity.repo_path),
        cwd=str(identity.repo_path),
        started_at="2026-04-30T00:00:00+00:00",
        model_name="test-model",
        instructions_text=None,
        prompt_text=None,
        metadata={},
    )
    return identity.project_id


def _create_record(
    store: ContextStore,
    *,
    project_id: str,
    kind: str,
    title: str,
) -> dict:
    """Create one active context record for tests."""
    return store.create_record(
        project_id=project_id,
        session_id="sess_working_memory",
        kind=kind,
        title=title,
        body=f"{title} body.",
        decision=title if kind == "decision" else None,
        why="Because it is the project choice." if kind == "decision" else None,
        user_intent="Understand recent work." if kind == "episode" else None,
        what_happened="A useful implementation detail was captured."
        if kind == "episode"
        else None,
    )


def test_resolve_working_memory_project_uses_most_specific_registered_path(tmp_path):
    """Cwd project resolution chooses the deepest registered project path."""
    parent = tmp_path / "parent"
    child = parent / "child"
    child.mkdir(parents=True)
    cfg = replace(
        make_config(tmp_path / ".lerim"),
        projects={"parent": str(parent), "child": str(child)},
    )

    resolved = resolve_working_memory_project(config=cfg, cwd=child / "src")

    assert resolved.name == "child"
    assert resolved.identity.repo_path == child.resolve()


def test_candidate_loading_prioritizes_durable_records(tmp_path, mock_embeddings):
    """Candidate ordering prefers decisions and constraints before episodes."""
    repo = tmp_path / "repo"
    repo.mkdir()
    store = ContextStore(tmp_path / "context.sqlite3")
    project_id = _register_seeded_project(store, repo)
    episode = _create_record(
        store,
        project_id=project_id,
        kind="episode",
        title="Debugged the workflow",
    )
    store.create_record(
        project_id=project_id,
        session_id="sess_working_memory",
        kind="decision",
        title="Older generated Working Memory decision",
        body="Older generated Working Memory decision body.",
        decision="Older generated Working Memory decision",
        why="Because older durable choices should follow newer ones.",
        created_at="2026-04-30T00:00:00+00:00",
        updated_at="2026-04-30T00:00:00+00:00",
    )
    newer_decision = store.create_record(
        project_id=project_id,
        session_id="sess_working_memory",
        kind="decision",
        title="Newer generated Working Memory decision",
        body="Newer generated Working Memory decision body.",
        decision="Newer generated Working Memory decision",
        why="Because the latest durable choice should lead.",
        created_at="2026-04-30T01:00:00+00:00",
        updated_at="2026-04-30T01:00:00+00:00",
    )

    candidates = load_candidate_records(store, project_id=project_id)

    assert candidates[0]["record_id"] == newer_decision["record_id"]
    assert candidates[-1]["record_id"] == episode["record_id"]


def test_candidate_loading_prefers_newer_records_within_kind(tmp_path, mock_embeddings):
    """Candidate ordering uses latest updated_at within the same record kind."""
    repo = tmp_path / "repo"
    repo.mkdir()
    store = ContextStore(tmp_path / "context.sqlite3")
    project_id = _register_seeded_project(store, repo)
    old_fact = store.create_record(
        project_id=project_id,
        session_id="sess_working_memory",
        kind="fact",
        title="Older fact",
        body="Older fact body.",
        created_at="2026-04-30T00:00:00+00:00",
        updated_at="2026-04-30T00:00:00+00:00",
    )
    new_fact = store.create_record(
        project_id=project_id,
        session_id="sess_working_memory",
        kind="fact",
        title="Newer fact",
        body="Newer fact body.",
        created_at="2026-04-30T01:00:00+00:00",
        updated_at="2026-04-30T01:00:00+00:00",
    )

    candidates = load_candidate_records(store, project_id=project_id)

    fact_ids = [row["record_id"] for row in candidates if row["kind"] == "fact"]
    assert fact_ids[:2] == [new_fact["record_id"], old_fact["record_id"]]


def test_rendered_markdown_contains_freshness_and_citations(tmp_path):
    """Renderer includes freshness fields and record citations."""
    repo = tmp_path / "repo"
    repo.mkdir()
    project = resolve_working_memory_project(
        config=replace(make_config(tmp_path / ".lerim"), projects={"repo": str(repo)}),
        cwd=repo,
    )
    draft = WorkingMemoryDraft(
        summary=(MemoryLine("Use generated Working Memory", ("rec_123",)),),
        sections=(
            MemorySection(
                "Decisions",
                (MemoryLine("Keep SQLite canonical", ("rec_456",)),),
            ),
        ),
    )

    markdown = render_working_memory_markdown(
        project=project,
        generated_at="2026-04-30T00:00:00+00:00",
        records_included=2,
        changed_since_generation=3,
        draft=draft,
    )

    assert "Records changed since generation: 3" in markdown
    assert "Use generated Working Memory [rec_123]" in markdown
    assert "Keep SQLite canonical [rec_456]" in markdown


def test_changed_record_count_uses_versions_since_baseline(tmp_path, mock_embeddings):
    """Freshness count tracks created records after the generation baseline."""
    repo = tmp_path / "repo"
    repo.mkdir()
    store = ContextStore(tmp_path / "context.sqlite3")
    project_id = _register_seeded_project(store, repo)
    baseline = "2026-04-30T00:00:00+00:00"
    created = _create_record(
        store,
        project_id=project_id,
        kind="decision",
        title="Newer decision",
    )

    count = count_changed_records_since(store, project_id=project_id, since=baseline)

    assert count == 1
    assert created["record_id"]


def test_runtime_refresh_writes_dated_and_current_artifacts(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    mock_embeddings,
):
    """Runtime refresh writes run-local and stable current artifacts."""
    repo = tmp_path / "repo"
    repo.mkdir()
    cfg = replace(make_config(tmp_path / ".lerim"), projects={"repo": str(repo)})
    store = ContextStore(cfg.context_db_path)
    project_id = _register_seeded_project(store, repo)
    record = _create_record(
        store,
        project_id=project_id,
        kind="decision",
        title="Generate cited startup context",
    )
    monkeypatch.setattr(
        "lerim.config.providers.validate_provider_for_role",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "lerim.server.runtime.build_pydantic_model",
        lambda *args, **kwargs: object(),
    )
    monkeypatch.setattr(
        "lerim.server.runtime.run_working_memory_synthesis",
        lambda **_kwargs: (
            WorkingMemoryDraft(
                summary=(
                    MemoryLine(
                        "Generate cited startup context",
                        (record["record_id"],),
                    ),
                ),
                sections=(),
            ),
            [],
        ),
    )

    runtime = LerimRuntime(default_cwd=str(repo), config=cfg)
    result = runtime.working_memory(repo_root=repo, project_name="repo", force=True)
    paths = working_memory_paths(cfg, project_id)

    assert result["status"] == "generated"
    assert paths.current_file.is_file()
    assert Path(result["run_folder"], "WORKING_MEMORY.md").is_file()
    assert record["record_id"] in paths.current_file.read_text(encoding="utf-8")


def test_cli_show_reads_existing_current_artifact(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CLI show prints the current file without invoking refresh."""
    repo = tmp_path / "repo"
    repo.mkdir()
    config_path = write_test_config(tmp_path, projects={"repo": str(repo)})
    monkeypatch.setenv("LERIM_CONFIG", str(config_path))
    from lerim.config.settings import reload_config

    cfg = reload_config()
    project_id = resolve_project_identity(repo).project_id
    paths = working_memory_paths(cfg, project_id)
    paths.current_dir.mkdir(parents=True)
    paths.current_file.write_text("# Working Memory\n\nhello\n", encoding="utf-8")
    monkeypatch.chdir(repo)
    monkeypatch.setattr(
        "lerim.server.cli.run_working_memory_for_project",
        lambda **_kwargs: pytest.fail("show must not refresh"),
    )

    code, output = run_cli(["working-memory", "show"])

    assert code == 0
    assert "hello" in output


def test_cli_status_json_reports_changed_records(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    mock_embeddings,
) -> None:
    """CLI status JSON exposes freshness metadata for scripts."""
    repo = tmp_path / "repo"
    repo.mkdir()
    config_path = write_test_config(tmp_path, projects={"repo": str(repo)})
    monkeypatch.setenv("LERIM_CONFIG", str(config_path))
    from lerim.config.settings import reload_config

    cfg = reload_config()
    store = ContextStore(cfg.context_db_path)
    project_id = _register_seeded_project(store, repo)
    paths = working_memory_paths(cfg, project_id)
    paths.current_dir.mkdir(parents=True)
    paths.current_file.write_text("# Working Memory\n", encoding="utf-8")
    paths.current_manifest.write_text(
        json.dumps(
            {
                "generated_at": "2026-04-30T00:00:00+00:00",
                "records_included": 0,
                "run_folder": str(tmp_path / "run"),
            }
        ),
        encoding="utf-8",
    )
    _create_record(
        store,
        project_id=project_id,
        kind="decision",
        title="New startup context choice",
    )
    monkeypatch.chdir(repo)

    code, payload = run_cli_json(["working-memory", "status", "--json"])

    assert code == 0
    assert payload["availability"] == "stale"
    assert payload["records_changed_since_generation"] == 1
