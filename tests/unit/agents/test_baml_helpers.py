"""Tests for shared BAML graph helpers."""

from __future__ import annotations

from enum import Enum

import pytest

from lerim.agents.baml_helpers import (
    call_baml_with_retries,
    instruction_with_validation_feedback,
    is_recoverable_baml_error,
    model_payload,
    model_retry_observation,
    plain_value,
)


class BamlValidationError(Exception):
    """Fake recoverable BAML validation error for retry tests."""


class NonRecoverableError(Exception):
    """Fake non-recoverable error for retry tests."""


class ExampleEnum(Enum):
    """Enum-like value used to verify JSON-ish conversion."""

    FACT = "fact"


class ExampleModel:
    """Minimal generated-client-shaped object."""

    def model_dump(self, *, exclude_none: bool) -> dict[str, object | None]:
        """Return a Pydantic-like payload."""
        assert exclude_none is True
        payload = {"kind": ExampleEnum.FACT, "empty": None, "tags": [ExampleEnum.FACT]}
        return {key: value for key, value in payload.items() if value is not None}


def test_model_payload_converts_generated_models_and_removes_none() -> None:
    payload = model_payload(ExampleModel())

    assert payload == {"kind": "fact", "tags": ["fact"]}


def test_plain_value_converts_nested_enums() -> None:
    payload = plain_value({"kind": ExampleEnum.FACT, "items": [ExampleEnum.FACT]})

    assert payload == {"kind": "fact", "items": ["fact"]}


def test_recoverable_error_detection_uses_baml_error_names() -> None:
    assert is_recoverable_baml_error(BamlValidationError("bad output")) is True
    assert is_recoverable_baml_error(NonRecoverableError("boom")) is False


def test_model_retry_observation_is_compact_json_guidance() -> None:
    content = model_retry_observation(BamlValidationError("bad\nshape"))

    assert "valid structured output" in content
    assert "<think>" in content
    assert "\n" not in content


def test_instruction_with_validation_feedback_appends_retry_guidance() -> None:
    instruction = instruction_with_validation_feedback(
        "Keep records compact.",
        "missing record_id",
        validation_retry_target="complete corrected action plan",
    )

    assert instruction.startswith("Keep records compact.")
    assert "missing record_id" in instruction
    assert "complete corrected action plan" in instruction


def test_call_baml_with_retries_retries_recoverable_baml_errors() -> None:
    calls = 0

    def flaky_call() -> dict[str, str]:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise BamlValidationError("bad shape")
        return {"ok": "yes"}

    result, observations, attempts = call_baml_with_retries(
        flaky_call,
        stage="scan_window",
        progress=False,
        progress_label="trace-ingestion",
    )

    assert result == {"ok": "yes"}
    assert attempts == 2
    assert observations[0]["action"] == "model_retry"


def test_call_baml_with_retries_adds_semantic_feedback_to_instruction() -> None:
    calls: list[str] = []

    def fake_call(instruction: str) -> dict[str, str]:
        calls.append(instruction)
        return {"ok": "yes"}

    result, observations, attempts = call_baml_with_retries(
        fake_call,
        stage="review_health",
        progress=False,
        progress_label="context-curator",
        run_instruction="Keep records compact.",
        validate_result=lambda _result: None if len(calls) > 1 else "missing record_id",
        validation_retry_target="complete corrected action plan",
    )

    assert result == {"ok": "yes"}
    assert attempts == 2
    assert len(observations) == 1
    assert "missing record_id" in calls[1]


def test_call_baml_with_retries_does_not_retry_non_recoverable_errors() -> None:
    with pytest.raises(NonRecoverableError):
        call_baml_with_retries(
            lambda: (_ for _ in ()).throw(NonRecoverableError("boom")),
            stage="scan_window",
            progress=False,
            progress_label="trace-ingestion",
        )
