"""Unit tests for the pi session adapter."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from lerim.adapters.pi import (
    compact_trace,
    count_sessions,
    default_path,
    iter_sessions,
    validate_connection,
)


def _write_jsonl(path: Path, entries: list[dict]) -> Path:
    """Write JSONL fixture entries."""
    with path.open("w", encoding="utf-8") as handle:
        for entry in entries:
            handle.write(json.dumps(entry) + "\n")
    return path


def _pi_session_entries(
    *,
    session_id: str = "pi-session-1",
    cwd: str = "/tmp/pi-project",
    timestamp: str = "2026-05-19T08:00:00.000Z",
) -> list[dict]:
    """Build a representative pi session fixture from the documented schema."""
    return [
        {
            "type": "session",
            "version": 3,
            "id": session_id,
            "timestamp": timestamp,
            "cwd": cwd,
        },
        {
            "type": "message",
            "id": "a1",
            "parentId": None,
            "timestamp": "2026-05-19T08:00:01.000Z",
            "message": {"role": "user", "content": "Remember the launch plan."},
        },
        {
            "type": "message",
            "id": "a2",
            "parentId": "a1",
            "timestamp": "2026-05-19T08:00:02.000Z",
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "thinking", "thinking": "private chain"},
                    {"type": "text", "text": "I will update the plan."},
                    {
                        "type": "toolCall",
                        "name": "bash",
                        "arguments": {"command": "ls"},
                    },
                ],
                "usage": {"inputTokens": 10, "outputTokens": 20},
            },
        },
        {
            "type": "message",
            "id": "a3",
            "parentId": "a2",
            "timestamp": "2026-05-19T08:00:03.000Z",
            "message": {
                "role": "toolResult",
                "toolName": "bash",
                "content": [{"type": "text", "text": "large output"}],
                "isError": False,
            },
        },
        {
            "type": "compaction",
            "id": "a4",
            "parentId": "a3",
            "timestamp": "2026-05-19T08:00:04.000Z",
            "summary": "Earlier context was compacted.",
            "tokensBefore": 50000,
        },
        {
            "type": "custom_message",
            "id": "a5",
            "parentId": "a4",
            "timestamp": "2026-05-19T08:00:05.000Z",
            "customType": "fixture",
            "content": "Injected extension context.",
            "display": True,
        },
        {
            "type": "session_info",
            "id": "a6",
            "parentId": "a5",
            "timestamp": "2026-05-19T08:00:06.000Z",
            "name": "Launch work",
        },
    ]


def test_default_path_returns_pi_session_root() -> None:
    """default_path points to pi's documented global session root."""
    path = default_path()
    assert path is not None
    assert str(path).endswith(".pi/agent/sessions")


def test_count_sessions_counts_non_empty_jsonl(tmp_path: Path) -> None:
    """count_sessions counts readable non-empty pi JSONL files."""
    (tmp_path / "a.jsonl").write_text("{}\n", encoding="utf-8")
    (tmp_path / "empty.jsonl").write_text("", encoding="utf-8")
    assert count_sessions(tmp_path) == 1


def test_validate_connection_reports_existing_path(tmp_path: Path) -> None:
    """validate_connection is advisory and reports session count."""
    (tmp_path / "a.jsonl").write_text("{}\n", encoding="utf-8")
    assert validate_connection(tmp_path) == {"ok": True, "sessions": 1}


def test_validate_connection_reports_missing_path(tmp_path: Path) -> None:
    """validate_connection reports a missing pi session directory."""
    missing = tmp_path / "missing"
    result = validate_connection(missing)
    assert result["ok"] is False
    assert str(missing) in result["error"]


def test_compact_trace_maps_pi_schema_to_canonical_entries() -> None:
    """compact_trace keeps context entries and clears bulky private blocks."""
    raw = "\n".join(json.dumps(entry) for entry in _pi_session_entries()) + "\n"
    result = compact_trace(raw)
    rows = [json.loads(line) for line in result.strip().splitlines()]

    assert [row["type"] for row in rows] == [
        "user",
        "assistant",
        "assistant",
        "assistant",
        "assistant",
    ]
    assistant_blocks = rows[1]["message"]["content"]
    assert assistant_blocks[0]["thinking"] == "[thinking cleared: 13 chars]"
    assert assistant_blocks[2] == {
        "type": "tool_use",
        "name": "bash",
        "input": {"command": "ls"},
    }
    tool_result = rows[2]["message"]["content"][0]
    assert tool_result["type"] == "tool_result"
    assert tool_result["content"] == "[cleared: 12 chars]"
    assert rows[3]["message"]["content"].startswith("[compaction summary]")


def test_compact_trace_handles_pi_edge_blocks() -> None:
    """pi compaction drops excluded bash output and redacts bulky blocks."""
    raw = "\n".join(
        json.dumps(entry)
        for entry in [
            {
                "type": "message",
                "timestamp": "2026-05-19T08:00:00.000Z",
                "message": {
                    "role": "bashExecution",
                    "command": "cat secret.txt",
                    "output": "secret output",
                    "excludeFromContext": True,
                },
            },
            {
                "type": "message",
                "timestamp": "2026-05-19T08:00:01.000Z",
                "message": {
                    "role": "bashExecution",
                    "command": "pytest",
                    "output": {"stdout": "failure"},
                    "exitCode": 1,
                },
            },
            {
                "type": "message",
                "timestamp": "2026-05-19T08:00:02.000Z",
                "message": {
                    "role": "assistant",
                    "content": [
                        {"type": "image", "mimeType": "image/png", "data": "large"},
                        {"type": "toolResult", "name": "read", "content": {"a": 1}},
                    ],
                },
            },
            {
                "type": "branch_summary",
                "timestamp": "2026-05-19T08:00:03.000Z",
                "summary": "Branch changed the integration path.",
            },
        ]
    )

    rows = [json.loads(line) for line in compact_trace(raw).strip().splitlines()]

    assert len(rows) == 3
    bash_block = rows[0]["message"]["content"][0]
    assert bash_block["name"] == "bash"
    assert bash_block["exit_code"] == 1
    assert bash_block["content"].startswith("[cleared:")
    image_block = rows[1]["message"]["content"][0]
    assert image_block == {
        "type": "image",
        "content": "[image cleared]",
        "mimeType": "image/png",
    }
    assert rows[2]["message"]["content"].startswith("[branch summary]")


def test_iter_sessions_counts_pi_errors(tmp_path: Path, monkeypatch) -> None:
    """iter_sessions counts nonzero pi bash executions as errors."""
    from tests.helpers import write_test_config

    config_path = write_test_config(tmp_path)
    monkeypatch.setenv("LERIM_CONFIG", str(config_path))

    traces = tmp_path / "sessions"
    traces.mkdir()
    entries = _pi_session_entries(session_id="with-error")
    entries.append(
        {
            "type": "message",
            "timestamp": "2026-05-19T08:00:07.000Z",
            "message": {
                "role": "bashExecution",
                "command": "pytest",
                "output": "failed",
                "exitCode": 2,
            },
        }
    )
    _write_jsonl(traces / "session.jsonl", entries)

    records = iter_sessions(traces_dir=traces)

    assert len(records) == 1
    assert records[0].error_count == 1


def test_iter_sessions_exports_compacted_cache(tmp_path: Path, monkeypatch) -> None:
    """iter_sessions returns SessionRecord rows backed by compact cache files."""
    from tests.helpers import write_test_config

    config_path = write_test_config(tmp_path)
    monkeypatch.setenv("LERIM_CONFIG", str(config_path))

    traces = tmp_path / "sessions"
    project = tmp_path / "project"
    traces.mkdir()
    project.mkdir()
    _write_jsonl(
        traces / "session.jsonl",
        _pi_session_entries(cwd=str(project), session_id="pi-fixture"),
    )

    records = iter_sessions(traces_dir=traces)

    assert len(records) == 1
    record = records[0]
    assert record.run_id == "pi-fixture"
    assert record.agent_type == "pi"
    assert record.repo_path == str(project)
    assert record.repo_name == "project"
    assert record.message_count == 3
    assert record.tool_call_count == 2
    assert record.error_count == 0
    assert record.total_tokens == 30
    assert record.content_hash
    cache_path = Path(record.session_path)
    assert cache_path.is_file()
    assert cache_path.parent.name == "pi"


def test_iter_sessions_window_filtering_and_known_ids(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """iter_sessions honors time windows and known run ids."""
    from tests.helpers import write_test_config

    config_path = write_test_config(tmp_path)
    monkeypatch.setenv("LERIM_CONFIG", str(config_path))

    traces = tmp_path / "sessions"
    traces.mkdir()
    _write_jsonl(
        traces / "early.jsonl",
        _pi_session_entries(
            session_id="early",
            timestamp="2026-01-01T00:00:00.000Z",
        ),
    )
    _write_jsonl(
        traces / "late.jsonl",
        _pi_session_entries(
            session_id="late",
            timestamp="2026-05-19T00:00:00.000Z",
        ),
    )

    start = datetime(2026, 5, 1, tzinfo=timezone.utc)
    records = iter_sessions(traces_dir=traces, start=start, known_run_ids={"late"})

    assert records == []
