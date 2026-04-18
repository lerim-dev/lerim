"""Unit tests for sqlite-vec semantic retrieval and migration behavior."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from lerim.context.project_identity import resolve_project_identity
from lerim.context.store import ContextStore
from tests.live_helpers import connect_context_db


class _FakeProvider:
    """Tiny deterministic embedding provider used for sqlite-vec store tests."""

    model_id = "test-embed-v1"
    embedding_dims = 4

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)

    def embed_document(self, text: str) -> list[float]:
        return self._vector(text)

    def _vector(self, text: str) -> list[float]:
        lowered = str(text or "").lower()
        if any(token in lowered for token in ("generic", "write api", "mutator", "explicit write")):
            return [1.0, 0.0, 0.0, 0.0]
        if any(token in lowered for token in ("cache", "redis", "ttl")):
            return [0.0, 1.0, 0.0, 0.0]
        return [0.0, 0.0, 1.0, 0.0]


def _build_store(tmp_path: Path, monkeypatch) -> tuple[ContextStore, str]:
    """Create a temp store with one registered project and fake provider."""
    monkeypatch.setattr("lerim.context.store.get_embedding_provider", lambda: _FakeProvider())
    db_path = tmp_path / "context.sqlite3"
    store = ContextStore(db_path)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    identity = resolve_project_identity(repo_root)
    store.initialize()
    store.register_project(identity)
    store.upsert_session(
        project_id=identity.project_id,
        session_id="sess_store",
        agent_type="test",
        source_trace_ref="seed:store",
        repo_path=str(repo_root),
        cwd=str(repo_root),
        started_at="2026-04-18T00:00:00+00:00",
        model_name="test-model",
        instructions_text=None,
        prompt_text=None,
        metadata={},
    )
    return store, identity.project_id


def test_initialize_migrates_plain_embedding_table_to_vec0(tmp_path, monkeypatch) -> None:
    """Old CSV embedding tables are dropped and replaced by vec0 storage."""
    monkeypatch.setattr("lerim.context.store.get_embedding_provider", lambda: _FakeProvider())
    db_path = tmp_path / "context.sqlite3"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE record_embeddings (
                record_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                embedding_model TEXT NOT NULL,
                embedding_csv TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.commit()

    store = ContextStore(db_path)
    store.initialize()

    with connect_context_db(db_path) as conn:
        sql = str(
            conn.execute("SELECT sql FROM sqlite_master WHERE name = 'record_embeddings'").fetchone()[0]
        )
        columns = {str(row[1]) for row in conn.execute("PRAGMA table_info(record_embeddings)").fetchall()}

    assert "vec0" in sql.lower()
    assert "embedding_csv" not in columns
    assert {"embedding", "project_id", "record_id", "embedding_model", "updated_at"} <= columns


def test_search_uses_semantic_vector_match_for_paraphrase(tmp_path, monkeypatch) -> None:
    """Paraphrase retrieval should work even when FTS terms do not overlap strongly."""
    store, project_id = _build_store(tmp_path, monkeypatch)
    store.create_record(
        project_id=project_id,
        session_id="sess_store",
        kind="decision",
        title="Replace mutator entrypoint",
        body="Use explicit record tools instead of one single mutator.",
        decision="Use explicit record tools",
        why="The single mutator caused malformed writes.",
    )
    store.create_record(
        project_id=project_id,
        session_id="sess_store",
        kind="fact",
        title="Redis cache backend",
        body="Redis handles the cache with TTL support.",
    )

    hits = store.search(
        project_ids=[project_id],
        query="why did we replace the generic write api",
        limit=5,
    )

    assert hits
    assert hits[0].title == "Replace mutator entrypoint"
    assert "semantic" in hits[0].sources
