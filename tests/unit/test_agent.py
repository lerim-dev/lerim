"""Unit tests for ask/maintain agents and runtime helpers (DB era)."""

from __future__ import annotations

from dataclasses import replace
import httpx
import pytest
from openai import RateLimitError

from lerim.agents.ask import ASK_SYSTEM_PROMPT, AskResult, format_ask_hints, run_ask
from lerim.agents.maintain import MAINTAIN_SYSTEM_PROMPT, MaintainResult, run_maintain
from lerim.context.project_identity import resolve_project_identity
from lerim.config.settings import RoleConfig
from lerim.server.runtime import (
	LerimRuntime,
	_is_quota_error_pydantic,
	build_maintain_artifact_paths,
)
from tests.helpers import make_config


def _make_rate_limit_error() -> RateLimitError:
	"""Build a real OpenAI RateLimitError for isinstance-based quota tests."""
	return RateLimitError(
		message="rate limited",
		response=httpx.Response(
			429,
			request=httpx.Request("POST", "https://test.local"),
		),
		body=None,
	)


def test_ask_system_prompt_mentions_db_tools() -> None:
	"""Ask prompt should guide the read-only DB retrieval flow."""
	assert "context_query" in ASK_SYSTEM_PROMPT
	assert "search_records" in ASK_SYSTEM_PROMPT
	assert "fetch_records" in ASK_SYSTEM_PROMPT
	assert "retrieved records only" in ASK_SYSTEM_PROMPT
	assert "historical truth" in ASK_SYSTEM_PROMPT


def test_maintain_system_prompt_mentions_semantic_mutations() -> None:
	"""Maintain prompt should talk about record mutations, not file edits."""
	assert "search_records" in MAINTAIN_SYSTEM_PROMPT
	assert "fetch_records" in MAINTAIN_SYSTEM_PROMPT
	assert "supersede_record" in MAINTAIN_SYSTEM_PROMPT
	assert "storage layout" in MAINTAIN_SYSTEM_PROMPT


def test_format_ask_hints_renders_hits() -> None:
	"""Hints formatter should include compact retrieval hits."""
	hints = format_ask_hints(
		hits=[
			{
				"kind": "decision",
				"title": "Auth policy",
				"body_preview": "Use short-lived access tokens and rotate refresh tokens.",
			},
		],
		context_docs=[],
	)
	assert "Auth policy" in hints
	assert "decision" in hints
	assert "rotate refresh tokens" in hints


def test_format_ask_hints_empty_has_placeholders() -> None:
	"""Empty inputs should still produce the DB-era placeholder text."""
	hints = format_ask_hints(hits=[], context_docs=[])
	assert hints == "(no pre-fetched hints)"


def test_run_ask_delegates_to_built_agent(monkeypatch, tmp_path) -> None:
	"""run_ask should pass prompt/deps/limits and return AskResult output."""
	captured: dict[str, object] = {}
	project_root = tmp_path / "repo"
	project_root.mkdir()
	project_identity = resolve_project_identity(project_root)

	class _FakeRunResult:
		def __init__(self) -> None:
			self.output = AskResult(answer="answer with citations")

		def all_messages(self):
			return []

	class _FakeAgent:
		def run_sync(self, prompt, *, deps, usage_limits):
			captured["prompt"] = prompt
			captured["deps"] = deps
			captured["request_limit"] = usage_limits.request_limit
			return _FakeRunResult()

	monkeypatch.setattr("lerim.agents.ask.build_ask_agent", lambda _model: _FakeAgent())
	result = run_ask(
		context_db_path=tmp_path / "context.sqlite3",
		project_identity=project_identity,
		project_ids=[project_identity.project_id],
		session_id="sess_ask",
		model=object(),
		question="What changed?",
		hints="hint block",
		request_limit=7,
	)
	assert result.answer == "answer with citations"
	assert "What changed?" in str(captured["prompt"])
	assert "hint block" in str(captured["prompt"])
	assert captured["request_limit"] == 7
	assert captured["deps"].session_id == "sess_ask"


def test_run_maintain_delegates_to_built_agent(monkeypatch, tmp_path) -> None:
	"""run_maintain should pass deps/limits and return MaintainResult output."""
	captured: dict[str, object] = {}
	project_root = tmp_path / "repo"
	project_root.mkdir()
	project_identity = resolve_project_identity(project_root)

	class _FakeRunResult:
		def __init__(self) -> None:
			self.output = MaintainResult(completion_summary="merged 2")

		def all_messages(self):
			return []

	class _FakeAgent:
		def run_sync(self, prompt, *, deps, usage_limits):
			captured["prompt"] = prompt
			captured["deps"] = deps
			captured["request_limit"] = usage_limits.request_limit
			return _FakeRunResult()

	monkeypatch.setattr(
		"lerim.agents.maintain.build_maintain_agent", lambda _model: _FakeAgent()
	)
	result = run_maintain(
		context_db_path=tmp_path / "context.sqlite3",
		project_identity=project_identity,
		session_id="sess_maintain",
		model=object(),
		request_limit=9,
	)
	assert result.completion_summary == "merged 2"
	assert "repairing weak records" in str(captured["prompt"])
	assert captured["request_limit"] == 9
	assert captured["deps"].session_id == "sess_maintain"


def test_runtime_init_and_missing_trace(tmp_path, monkeypatch) -> None:
	"""Runtime should initialize and keep missing trace behavior unchanged."""
	cfg = replace(make_config(tmp_path), openrouter_api_key="test-key")
	monkeypatch.setattr(
		"lerim.config.providers.validate_provider_for_role",
		lambda *args, **kwargs: None,
	)
	runtime = LerimRuntime(default_cwd=str(tmp_path), config=cfg)
	with pytest.raises(FileNotFoundError, match="trace_path_missing"):
		runtime.sync(trace_path=tmp_path / "missing.jsonl")


def test_runtime_generate_session_id_is_unique() -> None:
	"""Session IDs should have the expected prefix and be unique."""
	sid1 = LerimRuntime.generate_session_id()
	sid2 = LerimRuntime.generate_session_id()
	assert sid1.startswith("lerim-")
	assert sid2.startswith("lerim-")
	assert sid1 != sid2


def test_build_maintain_artifact_paths_keys(tmp_path) -> None:
	"""Maintain artifact helper should expose only expected keys."""
	paths = build_maintain_artifact_paths(tmp_path / "run")
	assert set(paths.keys()) == {"agent_log", "subagents_log"}


def test_is_quota_error_pydantic_detection() -> None:
	"""Quota/rate-limit classification should catch both typed and string errors."""
	assert _is_quota_error_pydantic(_make_rate_limit_error())
	assert _is_quota_error_pydantic(RuntimeError("HTTP 429 Too Many Requests"))
	assert _is_quota_error_pydantic(RuntimeError("quota exceeded"))
	assert not _is_quota_error_pydantic(RuntimeError("connection reset"))


def test_runtime_accepts_role_config_limits(tmp_path, monkeypatch) -> None:
	"""Role request limits should be read from config object."""
	cfg = make_config(tmp_path)
	cfg = replace(
		cfg,
		agent_role=RoleConfig(
			provider="openrouter",
			model="x-ai/grok-4.1-fast",
			max_iters_maintain=12,
			max_iters_ask=8,
		),
		openrouter_api_key="test-key",
	)
	monkeypatch.setattr(
		"lerim.config.providers.validate_provider_for_role",
		lambda *args, **kwargs: None,
	)
	rt = LerimRuntime(default_cwd=str(tmp_path), config=cfg)
	assert rt.config.agent_role.max_iters_maintain == 12
	assert rt.config.agent_role.max_iters_ask == 8
