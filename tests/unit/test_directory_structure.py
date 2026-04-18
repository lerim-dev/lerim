"""Tests for the DB-era Lerim storage layout.

Durable context now lives in one global SQLite database. Project repositories
should not need repo-local markdown context trees just to register, store, or
query context records.
"""

from __future__ import annotations

import sqlite3

import pytest

from lerim.context.project_identity import resolve_project_identity
from lerim.context.store import ContextStore
from tests.live_helpers import (
	FORBIDDEN_CONTEXT_TABLES,
	REQUIRED_CONTEXT_TABLES,
	connect_context_db,
	visible_context_tables,
)


def test_context_store_initialize_creates_global_sqlite_db(tmp_path):
	"""Context store initialization creates the canonical global DB file."""
	db_path = tmp_path / ".lerim" / "context.sqlite3"
	store = ContextStore(db_path)

	store.initialize()

	assert db_path.is_file()
	assert visible_context_tables(db_path) == REQUIRED_CONTEXT_TABLES
	assert not (visible_context_tables(db_path) & FORBIDDEN_CONTEXT_TABLES)


def test_register_project_uses_one_global_db_without_project_memory_dirs(tmp_path):
	"""Multiple repos register into one DB without creating repo-local markdown trees."""
	db_path = tmp_path / ".lerim" / "context.sqlite3"
	store = ContextStore(db_path)
	repo_a = tmp_path / "repo-a"
	repo_b = tmp_path / "repo-b"
	repo_a.mkdir()
	repo_b.mkdir()

	project_a = store.register_project(resolve_project_identity(repo_a))
	project_b = store.register_project(resolve_project_identity(repo_b))

	assert project_a["project_id"] != project_b["project_id"]

	with connect_context_db(db_path) as conn:
		project_rows = conn.execute(
			"SELECT project_id, repo_path FROM projects ORDER BY project_id"
		).fetchall()

	assert len(project_rows) == 2
	assert {str(row[1]) for row in project_rows} == {
		str(repo_a.resolve()),
		str(repo_b.resolve()),
	}
	assert not (repo_a / ".lerim" / "memory").exists()
	assert not (repo_b / ".lerim" / "memory").exists()


def test_records_live_in_context_db_not_in_project_markdown_tree(tmp_path):
	"""Writing a record persists into context.sqlite3 and not into repo folders."""
	db_path = tmp_path / ".lerim" / "context.sqlite3"
	store = ContextStore(db_path)
	repo = tmp_path / "repo"
	repo.mkdir()
	identity = resolve_project_identity(repo)

	store.register_project(identity)
	record = store.create_record(
		project_id=identity.project_id,
		session_id=None,
		kind="decision",
		title="Use one global context DB",
		body="Store durable Lerim context in the global SQLite database.",
		decision="Use one global context DB",
		why="Shared retrieval and history should live in one canonical store.",
	)

	with connect_context_db(db_path) as conn:
		db_count = conn.execute(
			"SELECT COUNT(*) FROM records WHERE project_id = ?",
			(identity.project_id,),
		).fetchone()[0]
		body = conn.execute(
			"SELECT body FROM records WHERE record_id = ?",
			(record["record_id"],),
		).fetchone()[0]

	assert db_count == 1
	assert "Store durable Lerim context" in str(body)
	assert not (repo / ".lerim" / "memory").exists()


def test_context_store_rejects_incompatible_db_schema(tmp_path):
	"""Incompatible context DB files now fail fast."""
	db_path = tmp_path / ".lerim" / "context.sqlite3"
	db_path.parent.mkdir(parents=True, exist_ok=True)

	with connect_context_db(db_path) as conn:
		conn.execute("CREATE TABLE records (record_id TEXT PRIMARY KEY, title TEXT)")
		conn.commit()

	store = ContextStore(db_path)
	with pytest.raises(sqlite3.Error):
		store.initialize()
