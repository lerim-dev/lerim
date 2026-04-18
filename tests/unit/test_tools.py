"""Unit tests for the DB-era Lerim agent tools."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic_ai.messages import ModelRequest, ModelResponse, SystemPromptPart, ToolCallPart, ToolReturnPart

from lerim.agents.tools import (
	CONTEXT_HARD_PRESSURE_PCT,
	CONTEXT_SOFT_PRESSURE_PCT,
	MODEL_CONTEXT_TOKEN_LIMIT,
	PRUNED_STUB,
	ContextDeps,
	Finding,
	compute_request_budget,
	context_apply,
	context_fetch,
	context_pressure_injector,
	context_search,
	note,
	notes_state_injector,
	prune,
	prune_history_processor,
	trace_read,
)
from lerim.context.project_identity import resolve_project_identity
from lerim.context.store import ContextStore


def _make_ctx(tmp_path: Path, *, trace_lines: list[str] | None = None):
	"""Build a minimal RunContext-like object for tool tests."""
	trace_path = tmp_path / "trace.jsonl"
	if trace_lines is None:
		trace_lines = [f'{{"turn": {idx}, "content": "message {idx}"}}' for idx in range(1, 21)]
	trace_path.write_text("\n".join(trace_lines), encoding="utf-8")
	project_root = tmp_path / "repo"
	project_root.mkdir()
	context_db_path = tmp_path / "context.sqlite3"
	identity = resolve_project_identity(project_root)
	deps = ContextDeps(
		context_db_path=context_db_path,
		project_identity=identity,
		session_id="sess_test",
		project_ids=[identity.project_id],
		trace_path=trace_path,
		run_folder=tmp_path / "run",
	)
	store = ContextStore(context_db_path)
	store.initialize()
	store.register_project(identity)
	store.upsert_session(
		project_id=identity.project_id,
		session_id=deps.session_id,
		agent_type="codex",
		source_trace_ref=str(trace_path),
		repo_path=str(project_root),
		cwd=str(project_root),
		started_at="2026-04-17T00:00:00Z",
		model_name="test-model",
		instructions_text="test",
		prompt_text="test",
		metadata={},
	)
	return SimpleNamespace(deps=deps), store


def test_trace_read_reads_numbered_chunk(tmp_path) -> None:
	"""trace_read returns a numbered chunk with pagination header."""
	ctx, _store = _make_ctx(tmp_path)

	result = trace_read(ctx, offset=2, limit=4)

	assert "[20 lines, showing 3-6]" in result
	assert "3\t" in result
	assert "6\t" in result


def test_trace_read_truncates_large_line(tmp_path) -> None:
	"""trace_read truncates oversized lines instead of flooding the prompt."""
	huge_line = "x" * 20_000
	ctx, _store = _make_ctx(tmp_path, trace_lines=[huge_line, "short"])

	result = trace_read(ctx, offset=0, limit=2)

	assert "[2 lines, showing 1-2]" in result
	assert "truncated" in result
	assert "short" in result


def test_note_persists_session_findings(tmp_path) -> None:
	"""note stores findings both in memory and in session_findings."""
	ctx, store = _make_ctx(tmp_path)

	result = note(
		ctx,
		[
			Finding(theme="caching", offset=4, quote="use redis", level="decision"),
			Finding(theme="caching", offset=8, quote="ttl needed", level="constraint"),
		],
	)

	assert "Noted 2 findings" in result
	assert len(ctx.deps.notes) == 2
	with store.connect() as conn:
		row = conn.execute("SELECT COUNT(1) AS total FROM session_findings").fetchone()
	assert int(row["total"]) == 2


def test_context_apply_create_search_and_fetch(tmp_path) -> None:
	"""Create, search, and fetch work together on the canonical store."""
	ctx, _store = _make_ctx(tmp_path)

	create_raw = context_apply(
		ctx,
		"create_record",
		{
			"kind": "decision",
			"domain": "project",
			"title": "Use Redis for cache",
			"summary": "Redis is the cache backend.",
			"structured": {
				"decision": "Use Redis for cache",
				"why": "Need TTL and persistence",
				"alternatives": ["Memcached"],
				"consequences": ["New Redis dependency"],
			},
			"evidence": [{"evidence_type": "trace_snippet", "snippet": "use redis"}],
		},
	)
	create_payload = json.loads(create_raw)
	record_id = create_payload["result"]["record_id"]

	search_payload = json.loads(context_search(ctx, query="redis ttl persistence"))
	assert search_payload["count"] >= 1
	assert any(hit["record_id"] == record_id for hit in search_payload["hits"])

	fetch_payload = json.loads(
		context_fetch(
			ctx,
			record_ids=[record_id],
			include_evidence=True,
			include_links=True,
			response_format="detailed",
		)
	)
	assert fetch_payload["count"] == 1


def test_context_apply_normalizes_default_domain_to_project(tmp_path) -> None:
	"""The semantic write tool should coerce generic default domain to project."""
	ctx, _store = _make_ctx(tmp_path)

	create_raw = context_apply(
		ctx,
		"create_record",
		{
			"kind": "decision",
			"domain": "default",
			"title": "Use SQLite context store",
			"summary": "One global DB is canonical.",
			"structured": {
				"decision": "Use SQLite context store",
				"why": "Need one durable source of truth",
			},
		},
	)
	create_payload = json.loads(create_raw)
	assert create_payload["ok"] is True
	assert create_payload["result"]["domain"] == "project"


def test_context_apply_update_and_link(tmp_path) -> None:
	"""Semantic updates and links create new durable state."""
	ctx, store = _make_ctx(tmp_path)
	first = json.loads(
		context_apply(
			ctx,
			"create_record",
			{
				"kind": "fact",
				"domain": "project",
				"title": "Current cache",
				"summary": "Cache uses Redis.",
				"structured": {"content": "Cache uses Redis."},
			},
		)
	)["result"]
	second = json.loads(
		context_apply(
			ctx,
			"create_record",
			{
				"kind": "decision",
				"domain": "project",
				"title": "Adopt cache invalidation policy",
				"summary": "Invalidate on writes.",
				"structured": {"decision": "Invalidate on writes", "why": "Keep cache fresh"},
			},
		)
	)["result"]

	update_payload = json.loads(
		context_apply(
			ctx,
			"update_record",
			{
				"record_id": first["record_id"],
				"changes": {"summary": "Cache uses Redis with TTL.", "structured": {"how_to_apply": "Set TTL on write"}},
				"change_reason": "clarify runtime behavior",
			},
		)
	)
	assert update_payload["result"]["summary"] == "Cache uses Redis with TTL."

	link_payload = json.loads(
		context_apply(
			ctx,
			"link_records",
			{
				"from_record_id": second["record_id"],
				"to_record_id": first["record_id"],
				"relation": "supports",
				"reason": "policy supports the active cache setup",
			},
		)
	)
	assert link_payload["result"]["relation"] == "supports"
	with store.connect() as conn:
		row = conn.execute("SELECT COUNT(1) AS total FROM record_links").fetchone()
	assert int(row["total"]) == 1


def test_context_apply_rejects_invalid_episode_record(tmp_path) -> None:
	"""Episode creation should require structured user intent and what happened."""
	ctx, _store = _make_ctx(tmp_path)

	result = context_apply(
		ctx,
		"create_record",
		{
			"kind": "episode",
			"domain": "session",
			"title": "Session summary",
			"summary": "Something happened.",
			"structured": {},
		},
	)

	assert result == "Error: invalid_episode_structured"


def test_context_apply_rejects_invalid_decision_record(tmp_path) -> None:
	"""Decision creation should require both the decision text and why."""
	ctx, _store = _make_ctx(tmp_path)

	result = context_apply(
		ctx,
		"create_record",
		{
			"kind": "decision",
			"domain": "project",
			"title": "Use Redis",
			"summary": "Redis is the cache backend.",
			"structured": {"decision": "Use Redis"},
		},
	)

	assert result == "Error: invalid_decision_structured"


def test_context_apply_rejects_duplicate_episode_for_same_session(tmp_path) -> None:
	"""One session should only produce one canonical episode record."""
	ctx, _store = _make_ctx(tmp_path)

	first = context_apply(
		ctx,
		"create_record",
		{
			"kind": "episode",
			"domain": "session",
			"title": "Episode one",
			"summary": "First summary.",
			"structured": {
				"user_intent": "Understand the system",
				"what_happened": "Read the codebase and mapped the flow.",
			},
		},
	)
	assert json.loads(first)["ok"] is True

	second = context_apply(
		ctx,
		"create_record",
		{
			"kind": "episode",
			"domain": "session",
			"title": "Episode two",
			"summary": "Second summary.",
			"structured": {
				"user_intent": "Understand the system",
				"what_happened": "Tried to write a second episode.",
			},
		},
	)

	assert second == "Error: duplicate_episode_for_session"


def test_context_fetch_respects_project_scope(tmp_path) -> None:
	"""Fetching by record id should not leak records across project boundaries."""
	ctx, store = _make_ctx(tmp_path)
	other_root = tmp_path / "other-repo"
	other_root.mkdir()
	other_identity = resolve_project_identity(other_root)
	store.register_project(other_identity)
	store.upsert_session(
		project_id=other_identity.project_id,
		session_id="sess_other",
		agent_type="codex",
		source_trace_ref=str(tmp_path / "other-trace.jsonl"),
		repo_path=str(other_root),
		cwd=str(other_root),
		started_at="2026-04-17T00:00:00Z",
		model_name="test-model",
		instructions_text="test",
		prompt_text="test",
		metadata={},
	)
	foreign = store.create_record(
		project_id=other_identity.project_id,
		session_id="sess_other",
		kind="fact",
		domain="project",
		title="Other project fact",
		summary="Private record",
		structured={"content": "Private record"},
	)

	payload = json.loads(context_fetch(ctx, [foreign["record_id"]], response_format="detailed"))

	assert payload["count"] == 0
	assert payload["records"] == []


def test_context_search_graph_expansion_respects_archived_filter(tmp_path) -> None:
	"""Graph expansion should not pull archived records into active-only search results."""
	ctx, _store = _make_ctx(tmp_path)
	active = json.loads(
		context_apply(
			ctx,
			"create_record",
			{
				"kind": "decision",
				"domain": "project",
				"title": "Use Redis",
				"summary": "Redis is active.",
				"structured": {"decision": "Use Redis", "why": "Need caching"},
			},
		)
	)["result"]
	archived = json.loads(
		context_apply(
			ctx,
			"create_record",
			{
				"kind": "fact",
				"domain": "project",
				"title": "Old Memcached note",
				"summary": "Memcached was used before.",
				"structured": {"content": "Memcached was used before."},
			},
		)
	)["result"]
	json.loads(
		context_apply(
			ctx,
			"archive_record",
			{"record_id": archived["record_id"], "reason": "obsolete"},
		)
	)
	json.loads(
		context_apply(
			ctx,
			"link_records",
			{
				"from_record_id": active["record_id"],
				"to_record_id": archived["record_id"],
				"relation": "related",
				"reason": "Historical context",
			},
		)
	)

	payload = json.loads(context_search(ctx, query="redis", limit=8))

	assert all(hit["record_id"] != archived["record_id"] for hit in payload["hits"])


def test_context_search_graph_expansion_respects_as_of_filter(tmp_path) -> None:
	"""Graph expansion should not pull records that were not valid at the requested time."""
	ctx, _store = _make_ctx(tmp_path)
	current = json.loads(
		context_apply(
			ctx,
			"create_record",
			{
				"kind": "decision",
				"domain": "project",
				"title": "Current cache decision",
				"summary": "Use Redis now.",
				"structured": {"decision": "Use Redis now", "why": "Need TTL"},
				"valid_from": "2026-04-10T00:00:00+00:00",
			},
		)
	)["result"]
	future = json.loads(
		context_apply(
			ctx,
			"create_record",
			{
				"kind": "fact",
				"domain": "project",
				"title": "Future migration note",
				"summary": "Move to cluster later.",
				"structured": {"content": "Move to cluster later."},
				"valid_from": "2026-05-01T00:00:00+00:00",
			},
		)
	)["result"]
	json.loads(
		context_apply(
			ctx,
			"link_records",
			{
				"from_record_id": current["record_id"],
				"to_record_id": future["record_id"],
				"relation": "related",
				"reason": "Future plan",
			},
		)
	)

	payload = json.loads(
		context_search(
			ctx,
			query="redis",
			as_of="2026-04-15T00:00:00+00:00",
			limit=8,
		)
	)

	assert all(hit["record_id"] != future["record_id"] for hit in payload["hits"])


def test_context_search_accepts_punctuation_heavy_query(tmp_path) -> None:
	"""Hybrid search should not crash on raw tool-like punctuation and file/version text."""
	ctx, _store = _make_ctx(tmp_path)
	record = json.loads(
		context_apply(
			ctx,
			"create_record",
			{
				"kind": "fact",
				"domain": "project",
				"title": "MiniMax model config",
				"summary": "Use MiniMax-M2.7 and ~/.lerim/context.sqlite3 for runtime.",
				"structured": {
					"content": "MiniMax-M2.7 and ~/.lerim/context.sqlite3 are part of the runtime config."
				},
			},
		)
	)["result"]

	payload = json.loads(
		context_search(ctx, query="MiniMax-M2.7 ~/.lerim/context.sqlite3 config.toml")
	)

	assert payload["count"] >= 1
	assert any(hit["record_id"] == record["record_id"] for hit in payload["hits"])


def test_context_search_ignores_punctuation_only_query(tmp_path) -> None:
	"""Pure punctuation should safely return no lexical hits instead of raising FTS errors."""
	ctx, _store = _make_ctx(tmp_path)

	payload = json.loads(context_search(ctx, query="... ::: ---"))

	assert payload["count"] == 0
	assert payload["hits"] == []


def test_context_apply_supersede_records_change_kind_and_returns_fresh_links(tmp_path) -> None:
	"""Supersede should create a supersede version and return the fresh linked record."""
	ctx, store = _make_ctx(tmp_path)
	old = json.loads(
		context_apply(
			ctx,
			"create_record",
			{
				"kind": "decision",
				"domain": "project",
				"title": "Use single Redis node",
				"summary": "Initial cache design.",
				"structured": {"decision": "Use single Redis node", "why": "Enough for now"},
			},
		)
	)["result"]
	new = json.loads(
		context_apply(
			ctx,
			"create_record",
			{
				"kind": "decision",
				"domain": "project",
				"title": "Use Redis cluster",
				"summary": "Scale the cache layer.",
				"structured": {"decision": "Use Redis cluster", "why": "Need higher availability"},
			},
		)
	)["result"]

	result = json.loads(
		context_apply(
			ctx,
			"supersede_record",
			{
				"record_id": old["record_id"],
				"replacement_record_id": new["record_id"],
				"reason": "scale requirements changed",
				"valid_until": "2026-04-17T12:00:00+00:00",
			},
		)
	)["result"]

	assert any(
		link["relation"] == "supersedes"
		and link["from_record_id"] == new["record_id"]
		and link["to_record_id"] == old["record_id"]
		for link in result["links"]
	)
	with store.connect() as conn:
		version = conn.execute(
			"""
			SELECT change_kind
			FROM record_versions
			WHERE record_id = ?
			ORDER BY version_no DESC
			LIMIT 1
			""",
			(old["record_id"],),
		).fetchone()
	assert version["change_kind"] == "supersede"


def test_prune_tracks_offsets(tmp_path) -> None:
	"""prune updates the in-run pruned offset set only."""
	ctx, _store = _make_ctx(tmp_path)

	result = prune(ctx, [0, 50, 50])

	assert "Pruned 2 new offset(s)" in result
	assert ctx.deps.pruned_offsets == {0, 50}


def test_notes_state_injector_adds_dashboard(tmp_path) -> None:
	"""notes_state_injector appends a compact notes summary request."""
	ctx, _store = _make_ctx(tmp_path)
	ctx.deps.notes.extend(
		[
			Finding(theme="auth", offset=1, quote="jwt", level="decision"),
			Finding(theme="auth", offset=2, quote="rotate", level="fact"),
		]
	)

	injected = notes_state_injector(ctx, history=[])

	assert len(injected) == 1
	message = injected[0]
	assert isinstance(message, ModelRequest)
	part = message.parts[0]
	assert isinstance(part, SystemPromptPart)
	assert "NOTES: 2 findings" in part.content
	assert "Top themes: auth(2)" in part.content


def test_context_pressure_injector_adds_pressure_summary(tmp_path) -> None:
	"""context_pressure_injector reports approximate token pressure."""
	ctx, _store = _make_ctx(tmp_path)
	chars = int(MODEL_CONTEXT_TOKEN_LIMIT * CONTEXT_SOFT_PRESSURE_PCT / 0.25) + 100
	history = [ModelRequest(parts=[SystemPromptPart(content="x" * chars)])]

	injected = context_pressure_injector(ctx, history)

	assert len(injected) == 2
	part = injected[-1].parts[0]
	assert "CONTEXT:" in part.content
	assert "[soft]" in part.content or "[hard]" in part.content


def test_prune_history_processor_rewrites_pruned_trace_returns(tmp_path) -> None:
	"""prune_history_processor replaces old trace chunks with a stub."""
	ctx, _store = _make_ctx(tmp_path)
	ctx.deps.pruned_offsets.add(0)
	call = ToolCallPart(tool_name="trace_read", args={"offset": 0, "limit": 10})
	other_call = ToolCallPart(tool_name="trace_read", args={"offset": 10, "limit": 10})
	history = [
		ModelRequest(parts=[call]),
		ModelResponse(parts=[ToolReturnPart(tool_name="trace_read", content="chunk 0")]),
		ModelRequest(parts=[other_call]),
		ModelResponse(parts=[ToolReturnPart(tool_name="trace_read", content="chunk 10")]),
	]

	rewritten = prune_history_processor(ctx, history)

	first_return = rewritten[1].parts[0]
	second_return = rewritten[3].parts[0]
	assert isinstance(first_return, ToolReturnPart)
	assert first_return.content == PRUNED_STUB
	assert second_return.content == "chunk 10"


@pytest.mark.parametrize(
	("line_count", "expected"),
	[
		(10, 40),
		(240, 42),
		(5000, 100),
	],
)
def test_compute_request_budget_scales_with_trace_size(tmp_path, line_count: int, expected: int) -> None:
	"""Request budget should grow with trace size within the configured bounds."""
	trace_path = tmp_path / "trace.jsonl"
	trace_path.write_text("\n".join(f"line {idx}" for idx in range(line_count)), encoding="utf-8")

	assert compute_request_budget(trace_path) == expected
