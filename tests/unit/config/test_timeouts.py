"""Tests for shared timeout contracts."""

from __future__ import annotations

from pathlib import Path

from lerim.config.timeouts import (
    ANSWER_REQUEST_TIMEOUT_SECONDS,
    BAML_HTTP_IDLE_TIMEOUT_MS,
    BAML_HTTP_REQUEST_TIMEOUT_MS,
    BAML_HTTP_TIME_TO_FIRST_TOKEN_TIMEOUT_MS,
    HTTP_API_POST_TIMEOUT_SECONDS,
)
from lerim.server.cli_api_client import API_POST_TIMEOUT_SECONDS

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_answer_timeout_is_five_minutes() -> None:
    """The answer endpoint timeout is the user-visible five-minute ceiling."""
    assert ANSWER_REQUEST_TIMEOUT_SECONDS == 300


def test_cli_timeout_allows_server_answer_deadline() -> None:
    """The CLI waits long enough for the server to return its answer timeout."""
    assert API_POST_TIMEOUT_SECONDS == HTTP_API_POST_TIMEOUT_SECONDS
    assert API_POST_TIMEOUT_SECONDS > ANSWER_REQUEST_TIMEOUT_SECONDS


def test_baml_answer_model_timeouts_align_with_answer_deadline() -> None:
    """Model transport timeouts should not fail before the answer deadline."""
    deadline_ms = ANSWER_REQUEST_TIMEOUT_SECONDS * 1_000
    assert BAML_HTTP_TIME_TO_FIRST_TOKEN_TIMEOUT_MS == deadline_ms
    assert BAML_HTTP_IDLE_TIMEOUT_MS == deadline_ms
    assert BAML_HTTP_REQUEST_TIMEOUT_MS == deadline_ms


def test_baml_source_model_timeouts_align_with_answer_deadline() -> None:
    """The checked-in BAML model source should match the runtime timeout contract."""
    deadline_ms = ANSWER_REQUEST_TIMEOUT_SECONDS * 1_000
    content = (REPO_ROOT / "src/lerim/agents/baml_src/models.baml").read_text(
        encoding="utf-8"
    )
    assert f"time_to_first_token_timeout_ms {deadline_ms}" in content
    assert f"idle_timeout_ms {deadline_ms}" in content
    assert f"request_timeout_ms {deadline_ms}" in content
