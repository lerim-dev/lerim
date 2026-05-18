"""Shared helpers for BAML-backed agent graphs."""

from __future__ import annotations

from typing import Any, Callable

MAX_BAML_MODEL_RETRIES = 3
BAML_RECOVERABLE_ERROR_NAMES = {
    "BamlClientFinishReasonError",
    "BamlClientHttpError",
    "BamlTimeoutError",
    "BamlValidationError",
}


def call_baml_with_retries(
    call: Callable[..., Any],
    *,
    stage: str,
    progress: bool,
    progress_label: str,
    run_instruction: str | None = None,
    validate_result: Callable[[Any], str | None] | None = None,
    make_observation: Callable[[str, bool, str, dict[str, Any]], dict[str, Any]]
    | None = None,
    semantic_retry_content: Callable[[str], str] | None = None,
    validation_retry_target: str = "complete corrected output",
    raise_on_validation_failure: bool = True,
) -> tuple[Any, list[dict[str, Any]], int]:
    """Run one BAML call with recoverable retries and graph-visible observations."""
    observations: list[dict[str, Any]] = []
    attempts = 0
    validation_feedback = ""
    while True:
        attempts += 1
        try:
            result = _invoke_baml_call(
                call,
                run_instruction=run_instruction,
                validation_feedback=validation_feedback,
                validation_retry_target=validation_retry_target,
            )
        except Exception as exc:
            if not is_recoverable_baml_error(exc) or attempts > MAX_BAML_MODEL_RETRIES:
                raise
            if progress:
                print(f"  {progress_label} retry {stage} attempt={attempts}", flush=True)
            observations.append(
                _observation(
                    make_observation,
                    "model_retry",
                    False,
                    model_retry_observation(exc),
                    {"stage": stage, "attempt": attempts},
                )
            )
            continue
        if validate_result is None:
            return result, observations, attempts
        validation_error = validate_result(result)
        if not validation_error:
            return result, observations, attempts
        observations.append(
            _observation(
                make_observation,
                "model_retry",
                False,
                (
                    semantic_retry_content(validation_error)
                    if semantic_retry_content
                    else f"baml_validation_failed: {validation_error}"
                ),
                {"stage": stage, "attempt": attempts},
            )
        )
        if attempts > MAX_BAML_MODEL_RETRIES:
            if raise_on_validation_failure:
                raise RuntimeError(
                    f"BAML returned invalid {stage} output after "
                    f"{MAX_BAML_MODEL_RETRIES} retries: {validation_error}"
                )
            return result, observations, attempts
        validation_feedback = validation_error
        if progress:
            print(f"  {progress_label} retry {stage} attempt={attempts}", flush=True)


def model_payload(value: Any) -> dict[str, Any]:
    """Convert generated BAML objects into plain dictionaries."""
    if hasattr(value, "model_dump"):
        return plain_value(value.model_dump(exclude_none=True))
    if isinstance(value, dict):
        return plain_value({key: item for key, item in value.items() if item is not None})
    if value is None:
        return {}
    return plain_value(getattr(value, "__dict__", {}))


def plain_value(value: Any) -> Any:
    """Convert enums and generated model values into JSON-like values."""
    enum_value = getattr(value, "value", None)
    if enum_value is not None:
        return enum_value
    if isinstance(value, dict):
        return {key: plain_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [plain_value(item) for item in value]
    return value


def is_recoverable_baml_error(exc: Exception) -> bool:
    """Return whether a BAML model/parsing failure should be retried."""
    return type(exc).__name__ in BAML_RECOVERABLE_ERROR_NAMES


def model_retry_observation(exc: Exception) -> str:
    """Render a compact model failure note."""
    message = str(exc).replace("\n", " ")[:1200]
    return (
        "The previous BAML model call did not produce valid structured output. "
        "Retry and return exactly one JSON object matching the requested schema. "
        "Do not include <think> tags, hidden reasoning, markdown, or prose before "
        f"the JSON. Error: {type(exc).__name__}: {message}"
    )


def instruction_with_validation_feedback(
    run_instruction: str,
    validation_feedback: str,
    *,
    validation_retry_target: str,
) -> str:
    """Add compact validation feedback to a retry instruction."""
    if not validation_feedback:
        return run_instruction
    return (
        f"{run_instruction}\n\n"
        "Previous structured output was unsafe or incomplete. "
        f"Fix this validation error and return a {validation_retry_target}: "
        f"{validation_feedback}"
    )


def _invoke_baml_call(
    call: Callable[..., Any],
    *,
    run_instruction: str | None,
    validation_feedback: str,
    validation_retry_target: str,
) -> Any:
    """Call a zero-arg or instruction-arg BAML function."""
    if run_instruction is None:
        return call()
    return call(
        instruction_with_validation_feedback(
            run_instruction,
            validation_feedback,
            validation_retry_target=validation_retry_target,
        )
    )


def _observation(
    make_observation: Callable[[str, bool, str, dict[str, Any]], dict[str, Any]]
    | None,
    action: str,
    ok: bool,
    content: str,
    args: dict[str, Any],
) -> dict[str, Any]:
    """Create a graph observation using the caller's shape when provided."""
    if make_observation is not None:
        return make_observation(action, ok, content, args)
    return {
        "action": action,
        "ok": ok,
        "content": content,
        "args": args,
        "done": False,
        "completion_summary": "",
    }
