"""Tests for the `lerim feedback` CLI command.

Covers parser registration/wiring and the `_cmd_feedback` handler with a
mocked `api_feedback`, plus one end-to-end pass through `cli.main`.
"""

from __future__ import annotations

import argparse
import json

import pytest

from lerim.server import cli
from tests.helpers import run_cli, run_cli_json


def _get_subparser_names() -> set[str]:
    """Extract subcommand names from build_parser()."""
    parser = cli.build_parser()
    for action in parser._subparsers._actions:
        if isinstance(action, argparse._SubParsersAction):
            return set(action.choices.keys())
    return set()


# ── Parser registration and wiring ───────────────────────────────────


def test_feedback_parser_exists() -> None:
    """'feedback' is registered as a subcommand in build_parser()."""
    assert "feedback" in _get_subparser_names()


def test_feedback_parser_accepts_record_id_and_signal() -> None:
    """record_id and signal are positional arguments."""
    parser = cli.build_parser()
    args = parser.parse_args(["feedback", "rec_abc123", "correct"])
    assert args.command == "feedback"
    assert args.record_id == "rec_abc123"
    assert args.signal == "correct"
    assert args.note is None
    assert args.func is cli._cmd_feedback


@pytest.mark.parametrize("signal", ["used", "correct", "wrong", "confirm"])
def test_feedback_parser_accepts_all_allowed_signals(signal: str) -> None:
    """Every canonical feedback signal is a valid positional choice."""
    parser = cli.build_parser()
    args = parser.parse_args(["feedback", "rec_abc123", signal])
    assert args.signal == signal


def test_feedback_parser_rejects_invalid_signal() -> None:
    """Signals outside the canonical set are rejected by argparse."""
    parser = cli.build_parser()
    with pytest.raises(SystemExit) as exc:
        parser.parse_args(["feedback", "rec_abc123", "bogus"])
    assert exc.value.code == 2


def test_feedback_parser_accepts_note_and_json() -> None:
    """--note and --json are recognised optional flags."""
    parser = cli.build_parser()
    args = parser.parse_args(
        ["feedback", "rec_abc123", "wrong", "--note", "Reverted in prod", "--json"]
    )
    assert args.note == "Reverted in prod"
    assert args.json is True


def test_feedback_parser_requires_record_id_and_signal() -> None:
    """Both positionals are required."""
    parser = cli.build_parser()
    with pytest.raises(SystemExit) as exc:
        parser.parse_args(["feedback"])
    assert exc.value.code == 2
    with pytest.raises(SystemExit) as exc:
        parser.parse_args(["feedback", "rec_abc123"])
    assert exc.value.code == 2


# ── _cmd_feedback behaviour ───────────────────────────────────────────


def test_cmd_feedback_success_json(monkeypatch: pytest.MonkeyPatch) -> None:
    """A successful feedback call with --json prints the payload and exits 0."""
    captured: dict[str, object] = {}

    def fake_api_feedback(record_id, signal, *, note=None, source_session_id=None):
        captured["record_id"] = record_id
        captured["signal"] = signal
        captured["note"] = note
        return {
            "record_id": record_id,
            "confidence": 0.65,
            "signal": signal,
            "error": False,
            "projects_used": [],
            "scope": "all",
        }

    monkeypatch.setattr(cli, "api_feedback", fake_api_feedback)
    output: list[str] = []
    monkeypatch.setattr(cli, "_emit", lambda *a, **kw: output.append(str(a[0]) if a else ""))

    args = argparse.Namespace(
        record_id="rec_abc123", signal="correct", note="Confirmed", json=True
    )
    rc = cli._cmd_feedback(args)

    assert rc == 0
    assert captured == {"record_id": "rec_abc123", "signal": "correct", "note": "Confirmed"}
    payload = json.loads("\n".join(output))
    assert payload["confidence"] == 0.65
    assert payload["error"] is False


def test_cmd_feedback_success_without_json_flag_still_prints_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Successful feedback prints the JSON payload even without --json (mirrors query)."""
    monkeypatch.setattr(
        cli,
        "api_feedback",
        lambda *a, **kw: {
            "record_id": "rec_abc123",
            "confidence": 0.55,
            "signal": "used",
            "error": False,
            "projects_used": [],
            "scope": "all",
        },
    )
    output: list[str] = []
    monkeypatch.setattr(cli, "_emit", lambda *a, **kw: output.append(str(a[0]) if a else ""))

    args = argparse.Namespace(record_id="rec_abc123", signal="used", note=None, json=False)
    rc = cli._cmd_feedback(args)

    assert rc == 0
    payload = json.loads("\n".join(output))
    assert payload["confidence"] == 0.55


def test_cmd_feedback_error_json_returns_one(monkeypatch: pytest.MonkeyPatch) -> None:
    """A failed feedback call with --json prints the error payload and exits 1."""
    monkeypatch.setattr(
        cli,
        "api_feedback",
        lambda *a, **kw: {
            "error": True,
            "message": "record_not_found:rec_missing",
            "projects_used": [],
            "status_code": 400,
        },
    )
    output: list[str] = []
    monkeypatch.setattr(cli, "_emit", lambda *a, **kw: output.append(str(a[0]) if a else ""))

    args = argparse.Namespace(record_id="rec_missing", signal="correct", note=None, json=True)
    rc = cli._cmd_feedback(args)

    assert rc == 1
    payload = json.loads("\n".join(output))
    assert payload["error"] is True
    assert payload["message"] == "record_not_found:rec_missing"


def test_cmd_feedback_missing_record_error_without_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A missing-record error without --json prints the message to stderr and exits 1."""
    monkeypatch.setattr(
        cli,
        "api_feedback",
        lambda *a, **kw: {
            "error": True,
            "message": "record_not_found:rec_missing",
            "projects_used": [],
            "status_code": 400,
        },
    )
    stderr_lines: list[str] = []
    stdout_lines: list[str] = []

    def fake_emit(message="", *, file=None):
        (stderr_lines if file is not None else stdout_lines).append(str(message))

    monkeypatch.setattr(cli, "_emit", fake_emit)

    args = argparse.Namespace(record_id="rec_missing", signal="correct", note=None, json=False)
    rc = cli._cmd_feedback(args)

    assert rc == 1
    assert any("record_not_found:rec_missing" in line for line in stderr_lines)
    assert stdout_lines == []


def test_cmd_feedback_passes_note_through(monkeypatch: pytest.MonkeyPatch) -> None:
    """The optional --note value reaches api_feedback."""
    captured: dict[str, object] = {}

    def fake_api_feedback(record_id, signal, *, note=None, source_session_id=None):
        captured["note"] = note
        return {"record_id": record_id, "confidence": 0.5, "signal": signal, "error": False}

    monkeypatch.setattr(cli, "api_feedback", fake_api_feedback)
    monkeypatch.setattr(cli, "_emit", lambda *a, **kw: None)

    args = argparse.Namespace(record_id="rec_abc123", signal="confirm", note=None, json=True)
    cli._cmd_feedback(args)

    assert captured["note"] is None


# ── End-to-end through cli.main ───────────────────────────────────────


def test_feedback_end_to_end_through_main(monkeypatch: pytest.MonkeyPatch) -> None:
    """`lerim feedback <id> <signal> --json` runs through the real argparse + dispatch path."""
    monkeypatch.setattr(
        cli,
        "api_feedback",
        lambda record_id, signal, **kw: {
            "record_id": record_id,
            "confidence": 0.65,
            "signal": signal,
            "error": False,
            "projects_used": [],
            "scope": "all",
        },
    )
    code, payload = run_cli_json(["feedback", "rec_abc123", "correct", "--json"])
    assert code == 0
    assert payload["record_id"] == "rec_abc123"
    assert payload["confidence"] == 0.65


def test_feedback_end_to_end_error_exit_code(monkeypatch: pytest.MonkeyPatch) -> None:
    """A feedback failure surfaced through cli.main exits non-zero without --json."""
    monkeypatch.setattr(
        cli,
        "api_feedback",
        lambda *a, **kw: {
            "error": True,
            "message": "invalid_feedback_signal:bogus",
            "projects_used": [],
            "status_code": 400,
        },
    )
    code, _output = run_cli(["feedback", "rec_abc123", "correct"])
    assert code == 1
