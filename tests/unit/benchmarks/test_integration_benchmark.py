"""Unit tests for MCP integration benchmark report helpers."""

from __future__ import annotations

import json
from pathlib import Path

from benchmarks.lerim_evidence.integration import (
    CONFIG_PROBE,
    EXPECTED_MCP_TOOLS,
    INSTALLED_CLIENT_PROBE,
    REAL_DOCTOR_PROBE,
    STDIO_CONTEXT_TOOL_PROBE,
    STDIO_TRACE_SUBMIT_EXTRACTION_PROBE,
    STDIO_TRACE_SUBMIT_PROBE,
    STDIO_TOOLS_PROBE,
    TOOL_CALL_PROBE,
    build_report,
    parse_target_filter,
    run_tool_call_probe,
    render_markdown,
    write_outputs,
    _extract_structured_client_blocker,
    _extract_tool_names_from_text,
    _filter_probe_specs,
    _sanitize_public_payload,
)


def _config_detail(target: str, status: str = "pass") -> dict[str, object]:
    """Build one config probe detail row for pure report tests."""
    return {
        "probe": CONFIG_PROBE,
        "target": target,
        "display_name": target,
        "config_format": "json_mcp_servers",
        "status": status,
        "doctor": {"configured": status == "pass", "config_exists": True},
        "backup_created": True,
        "acceptance_scope": "temporary_config_fixture",
        "counts_as_installed_agent_acceptance": False,
    }


def _stdio_detail(status: str = "pass") -> dict[str, object]:
    """Build one stdio tools-list detail row for pure report tests."""
    tools = list(EXPECTED_MCP_TOOLS) if status == "pass" else []
    return {
        "probe": STDIO_TOOLS_PROBE,
        "target": "lerim-mcp-stdio",
        "display_name": "Lerim MCP stdio server",
        "status": status,
        "command": "python -m lerim.mcp_server",
        "tools": tools,
        "missing_tools": [] if status == "pass" else list(EXPECTED_MCP_TOOLS),
        "acceptance_scope": "local_stdio_server_tools_list_probe",
        "counts_as_installed_agent_acceptance": False,
    }


def _stdio_context_detail(status: str = "pass") -> dict[str, object]:
    """Build one stdio context tool-call row for pure report tests."""
    passed = status == "pass"
    return {
        "probe": STDIO_CONTEXT_TOOL_PROBE,
        "target": "lerim-mcp-stdio",
        "display_name": "Lerim MCP stdio server",
        "status": status,
        "command": "python -m lerim.mcp_server",
        "tool": "lerim_context_brief",
        "project": "lerim-cli",
        "project_id": "proj_fixture",
        "repo_path": "/tmp/lerim-cli",
        "availability": "available" if passed else None,
        "content_chars": 512 if passed else 0,
        "acceptance_scope": "local_stdio_server_context_tool_call",
        "counts_as_installed_agent_acceptance": False,
        "counts_as_local_context_tool_call_acceptance": passed,
    }


def _stdio_trace_submit_detail(status: str = "pass") -> dict[str, object]:
    """Build one stdio trace-submit row for pure report tests."""
    passed = status == "pass"
    return {
        "probe": STDIO_TRACE_SUBMIT_PROBE,
        "target": "lerim-mcp-stdio",
        "display_name": "Lerim MCP stdio server",
        "status": status,
        "command": "python -m lerim.mcp_server",
        "tool": "lerim_trace_submit",
        "result_status": "duplicate_skipped" if passed else "error",
        "session_id": "mcp-trace-submit-duplicate",
        "scope_type": "domain",
        "acceptance_scope": "local_stdio_server_trace_submit_duplicate_path",
        "counts_as_installed_agent_acceptance": False,
        "counts_as_trace_submit_idempotency_acceptance": passed,
        "counts_as_trace_submit_extraction_acceptance": False,
    }


def _stdio_trace_submit_extraction_detail(status: str = "pass") -> dict[str, object]:
    """Build one stdio trace-submit extraction row for pure report tests."""
    passed = status == "pass"
    return {
        "probe": STDIO_TRACE_SUBMIT_EXTRACTION_PROBE,
        "target": "lerim-mcp-stdio",
        "display_name": "Lerim MCP stdio server",
        "status": status,
        "command": "python -m lerim.mcp_server",
        "tool": "lerim_trace_submit",
        "result_status": "ingested" if passed else "error",
        "session_id": "mcp-trace-submit-extraction",
        "scope_type": "domain",
        "records_created": 2 if passed else 0,
        "record_count": 2 if passed else 0,
        "episode_record_count": 1 if passed else 0,
        "durable_record_count": 1 if passed else 0,
        "input_trace_kind": "synthetic_protocol_acceptance_trace",
        "acceptance_scope": "local_stdio_server_trace_submit_extraction_path",
        "counts_as_installed_agent_acceptance": False,
        "counts_as_trace_submit_idempotency_acceptance": False,
        "counts_as_trace_submit_extraction_acceptance": passed,
    }


def _installed_client_detail(
    target: str = "claude-code", status: str = "pass"
) -> dict[str, object]:
    """Build one installed-client probe detail row for pure report tests."""
    connected = status == "pass"
    return {
        "probe": INSTALLED_CLIENT_PROBE,
        "target": target,
        "display_name": target,
        "status": status,
        "command": ["claude", "mcp", "get", "lerim"],
        "connected": connected,
        "acceptance_scope": "real_installed_client_mcp_connection",
        "counts_as_installed_agent_acceptance": False,
        "counts_as_installed_client_connection_acceptance": connected,
    }


def _tool_call_detail(
    target: str = "claude-code", status: str = "pass"
) -> dict[str, object]:
    """Build one live tool-call probe detail row for pure report tests."""
    passed = status == "pass"
    row = {
        "probe": TOOL_CALL_PROBE,
        "target": target,
        "display_name": target,
        "status": status,
        "command": ["claude", "-p", "prompt"],
        "expected_tool": "lerim_context_brief",
        "observed_tools": ["mcp__lerim__lerim_context_brief"] if passed else [],
        "acceptance_scope": "real_installed_client_tool_call",
        "counts_as_installed_agent_acceptance": passed,
        "counts_as_context_tool_call_acceptance": passed,
    }
    if status == "blocked":
        row["blocker"] = {
            "reason": "external_client_error",
            "client_error_type": "CreditsError",
        }
    return row


def test_build_report_summarizes_all_known_temp_config_targets() -> None:
    """Report summary separates config fixture coverage from acceptance."""
    details = [
        _config_detail("codex"),
        _config_detail("gemini-cli"),
        _stdio_detail(),
        _stdio_context_detail(),
        _stdio_trace_submit_detail(),
    ]
    report = build_report(
        details,
        known_target_names=["codex", "gemini-cli"],
        generated_at="2026-05-19T00:00:00+00:00",
        environment={"git_commit": "abc123"},
    )

    assert report["overall_status"] == "pass"
    assert report["artifact_scope"] == "full_mcp_integration"
    assert report["is_full_integration_run"] is True
    assert report["summary"]["known_target_count"] == 2
    assert report["summary"]["config_passed_count"] == 2
    assert report["summary"]["stdio_passed_count"] == 1
    assert report["summary"]["stdio_context_tool_passed_count"] == 1
    assert report["summary"]["local_context_tool_call_acceptance_count"] == 1
    assert report["summary"]["stdio_trace_submit_passed_count"] == 1
    assert report["summary"]["trace_submit_idempotency_acceptance_count"] == 1
    assert report["summary"]["trace_submit_extraction_acceptance_count"] == 0
    assert report["summary"]["all_known_targets_checked"] is True
    assert report["summary"]["installed_agent_acceptance_count"] == 0
    assert report["summary"]["installed_client_probe_count"] == 0
    assert report["summary"]["tool_call_probe_count"] == 0
    assert report["required_artifacts"] == ["report.json", "report.md", "details.jsonl"]


def test_build_report_counts_real_installed_client_connections() -> None:
    """Report summary separates installed-client connection probes from fixtures."""
    report = build_report(
        [
            _config_detail("claude-code"),
            _stdio_detail(),
            _stdio_context_detail(),
            _stdio_trace_submit_detail(),
            _installed_client_detail(),
        ],
        known_target_names=["claude-code"],
        generated_at="2026-05-19T00:00:00+00:00",
        environment={},
    )

    assert report["overall_status"] == "pass"
    assert report["summary"]["installed_client_probe_count"] == 1
    assert report["summary"]["installed_client_connection_acceptance_count"] == 1
    assert report["summary"]["installed_agent_acceptance_count"] == 0


def test_build_report_counts_real_context_tool_calls() -> None:
    """Report summary separates real context tool-call acceptance."""
    report = build_report(
            [
                _config_detail("claude-code"),
                _stdio_detail(),
                _stdio_context_detail(),
                _stdio_trace_submit_detail(),
                _installed_client_detail(),
                _tool_call_detail(),
            ],
        known_target_names=["claude-code"],
        generated_at="2026-05-19T00:00:00+00:00",
        environment={},
    )

    assert report["overall_status"] == "pass"
    assert report["summary"]["tool_call_probe_count"] == 1
    assert report["summary"]["context_tool_call_acceptance_count"] == 1
    assert report["summary"]["installed_client_tool_call_acceptance_count"] == 1
    assert report["summary"]["installed_agent_acceptance_count"] == 1


def test_build_report_counts_stdio_trace_submit_extraction_acceptance() -> None:
    """Report summary counts real extraction acceptance separately."""
    report = build_report(
            [
                _config_detail("codex"),
                _stdio_detail(),
                _stdio_context_detail(),
                _stdio_trace_submit_detail(),
                _stdio_trace_submit_extraction_detail(),
            ],
        known_target_names=["codex"],
        generated_at="2026-05-19T00:00:00+00:00",
        environment={},
    )

    assert report["overall_status"] == "pass"
    assert report["summary"]["stdio_trace_submit_probe_count"] == 2
    assert report["summary"]["trace_submit_idempotency_acceptance_count"] == 1
    assert report["summary"]["trace_submit_extraction_acceptance_count"] == 1


def test_build_report_is_partial_when_stdio_context_probe_missing() -> None:
    """Full integration requires a local context tool-call acceptance."""
    report = build_report(
        [_config_detail("codex"), _stdio_detail(), _stdio_trace_submit_detail()],
        known_target_names=["codex"],
        generated_at="2026-05-19T00:00:00+00:00",
        environment={},
    )

    assert report["overall_status"] == "partial"
    assert report["is_full_integration_run"] is False
    assert report["artifact_scope"] == "partial_mcp_integration"


def test_build_report_is_partial_when_trace_submit_probe_missing() -> None:
    """Full integration requires the default trace-submit idempotency probe."""
    report = build_report(
        [_config_detail("codex"), _stdio_detail(), _stdio_context_detail()],
        known_target_names=["codex"],
        generated_at="2026-05-19T00:00:00+00:00",
        environment={},
    )

    assert report["overall_status"] == "partial"
    assert report["is_full_integration_run"] is False
    assert report["artifact_scope"] == "partial_mcp_integration"


def test_build_report_marks_external_client_blockers_as_partial() -> None:
    """Blocked live client probes are not counted as Lerim product failures."""
    report = build_report(
        [
            _config_detail("opencode"),
            _stdio_detail(),
            _stdio_context_detail(),
            _tool_call_detail(target="opencode", status="blocked"),
        ],
        known_target_names=["opencode"],
        generated_at="2026-05-19T00:00:00+00:00",
        environment={},
    )

    assert report["overall_status"] == "partial"
    assert report["summary"]["failure_count"] == 0
    assert report["summary"]["blocker_count"] == 1
    assert report["blockers"][0]["target"] == "opencode"


def test_build_report_fails_when_config_probe_fails() -> None:
    """A failed target probe is promoted into the top-level summary."""
    failed = _config_detail("codex", status="fail")
    failed["message"] = "verification did not match"
    report = build_report(
        [failed, _stdio_detail()],
        known_target_names=["codex"],
        generated_at="2026-05-19T00:00:00+00:00",
        environment={},
    )

    assert report["overall_status"] == "fail"
    assert report["summary"]["failure_count"] == 1
    assert report["failures"] == [
        {
            "probe": CONFIG_PROBE,
            "target": "codex",
            "status": "fail",
            "message": "verification did not match",
        }
    ]


def test_render_markdown_mentions_acceptance_boundary() -> None:
    """Generated Markdown keeps fixture results out of installed-agent claims."""
    report = build_report(
        [
            _config_detail("codex"),
            _stdio_detail(),
            _stdio_context_detail(),
            _stdio_trace_submit_detail(),
            _stdio_trace_submit_extraction_detail(),
        ],
        known_target_names=["codex"],
        generated_at="2026-05-19T00:00:00+00:00",
        environment={},
    )
    markdown = render_markdown(report)

    assert "# Lerim MCP Integration Benchmark" in markdown
    assert "Temporary config fixtures exercise Lerim writer and validation code paths" in markdown
    assert "## MCP Stdio Context Tool Call" in markdown
    assert "- Tool: `lerim_context_brief`" in markdown
    assert "## MCP Stdio Trace Submit" in markdown
    assert "- Tool: `lerim_trace_submit`" in markdown
    assert "- Probe: `stdio_mcp_trace_submit_extraction`" in markdown
    assert "- Durable records: `1`" in markdown
    assert "- Input trace: `synthetic_protocol_acceptance_trace`" in markdown
    assert "Installed-client context tool-call acceptances: `0`" in markdown
    assert "| codex | `pass` | `json_mcp_servers` | `yes` | `True` |" in markdown


def test_render_markdown_lists_installed_client_probes() -> None:
    """Generated Markdown summarizes installed-client MCP probe evidence."""
    report = build_report(
        [_config_detail("claude-code"), _stdio_detail(), _installed_client_detail()],
        known_target_names=["claude-code"],
        generated_at="2026-05-19T00:00:00+00:00",
        environment={},
    )
    markdown = render_markdown(report)

    assert "## Installed Client MCP CLI Probe Summary" in markdown
    assert "- Probe count: `1`" in markdown
    assert "- Connection acceptances: `1`" in markdown
    assert "claude mcp get lerim" not in markdown


def test_render_markdown_lists_tool_call_probes() -> None:
    """Generated Markdown summarizes installed-client tool-call evidence."""
    report = build_report(
        [_config_detail("claude-code"), _stdio_detail(), _tool_call_detail()],
        known_target_names=["claude-code"],
        generated_at="2026-05-19T00:00:00+00:00",
        environment={},
    )
    markdown = render_markdown(report)

    assert "## Installed Client Tool-Call Probe Summary" in markdown
    assert "- Context tool-call acceptances: `1`" in markdown
    assert "mcp__lerim__lerim_context_brief" in markdown
    assert "| claude-code | `pass` | `lerim_context_brief` |" not in markdown


def test_extract_tool_names_from_structured_client_output() -> None:
    """Tool-call parser reads structured JSONL events instead of prose."""
    payload = (
        '{"type":"assistant","message":{"content":[{"type":"tool_use",'
        '"name":"mcp__lerim__lerim_context_brief"}]}}\n'
        '{"type":"result","result":"ok"}\n'
    )

    assert _extract_tool_names_from_text(payload) == {"mcp__lerim__lerim_context_brief"}


def test_extract_tool_names_ignores_metadata_name_mentions() -> None:
    """Tool-call parser does not count structured metadata as tool use."""
    payload = '{"metadata":{"name":"mcp__lerim__lerim_context_brief"}}\n'

    assert _extract_tool_names_from_text(payload) == set()


def test_extract_structured_client_blocker_from_error_event() -> None:
    """Client API errors are classified from structured output fields."""
    payload = {
        "type": "error",
        "error": {
            "name": "APIError",
            "data": {
                "statusCode": 401,
                "responseBody": json.dumps(
                    {
                        "type": "error",
                        "error": {"type": "CreditsError"},
                    }
                ),
            },
        },
    }

    assert _extract_structured_client_blocker(json.dumps(payload)) == {
        "reason": "external_client_error",
        "client_error_type": "CreditsError",
        "client_error_name": "APIError",
        "status_code": 401,
    }


def test_extract_structured_client_blocker_from_api_status_event() -> None:
    """Client auth failures are classified from structured status fields."""
    payload = {
        "type": "result",
        "is_error": True,
        "api_error_status": 401,
        "error": "authentication_failed",
    }

    assert _extract_structured_client_blocker(json.dumps(payload)) == {
        "reason": "external_client_api_unavailable",
        "client_error_name": "authentication_failed",
        "status_code": 401,
    }


def test_parse_target_filter_normalizes_comma_separated_targets() -> None:
    """Target filter parsing trims blanks and preserves target names."""
    assert parse_target_filter("claude-code, gemini-cli,,") == {
        "claude-code",
        "gemini-cli",
    }
    assert parse_target_filter(None) is None
    assert parse_target_filter(" , ") is None


def test_filter_probe_specs_validates_unknown_targets() -> None:
    """Probe target filtering fails loudly for unknown names."""
    specs = (
        {"target": "claude-code"},
        {"target": "gemini-cli"},
    )

    assert _filter_probe_specs(
        specs,
        {"gemini-cli"},
        label="tool-call probe",
    ) == [{"target": "gemini-cli"}]

    try:
        _filter_probe_specs(specs, {"missing"}, label="tool-call probe")
    except SystemExit as exc:
        assert "Unknown tool-call probe target(s): missing" in str(exc)
    else:
        raise AssertionError("expected SystemExit for unknown target")


def test_tool_call_probe_skips_without_explicit_live_opt_in() -> None:
    """Live tool-call probes are skipped unless explicitly allowed."""
    result = run_tool_call_probe(
        {
            "target": "claude-code",
            "display_name": "Claude Code",
            "command": ["claude", "-p", "prompt"],
            "expected_tool": "lerim_context_brief",
        },
        allow_live_client_tool_calls=False,
        timeout_seconds=1.0,
        max_budget_usd=0.25,
    )

    assert result["status"] == "skip"
    assert result["counts_as_context_tool_call_acceptance"] is False


def test_write_outputs_creates_json_markdown_and_details_jsonl(tmp_path: Path) -> None:
    """Output writer emits the required source and generated artifacts."""
    details = [_config_detail("codex"), _stdio_detail()]
    report = build_report(
        details,
        known_target_names=["codex"],
        generated_at="2026-05-19T00:00:00+00:00",
        environment={},
    )

    write_outputs(tmp_path, report, details)

    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "details.jsonl",
        "report.json",
        "report.md",
    ]
    assert json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))["summary"][
        "config_passed_count"
    ] == 1
    detail_rows = [
        json.loads(line)
        for line in (tmp_path / "details.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [row["probe"] for row in detail_rows] == [CONFIG_PROBE, STDIO_TOOLS_PROBE]
    assert (tmp_path / "report.md").read_text(encoding="utf-8").endswith("\n")


def test_public_outputs_omit_local_installed_client_inventory(tmp_path: Path) -> None:
    """Public MCP artifacts preserve counts without publishing local client inventory."""
    home = str(Path.home())
    details = [
        _config_detail("codex"),
        {
            "probe": REAL_DOCTOR_PROBE,
            "target": "opencode",
            "display_name": "OpenCode",
            "status": "pass",
            "doctor": {
                "config_path": f"{home}/.config/opencode/opencode.json",
                "configured": True,
                "detected": True,
            },
            "acceptance_scope": "real_config_read_only_observation",
            "counts_as_installed_agent_acceptance": False,
        },
        _installed_client_detail(target="claude-code"),
    ]
    report = build_report(
        details,
        known_target_names=["codex", "opencode", "claude-code"],
        generated_at="2026-05-19T00:00:00+00:00",
        environment={},
    )

    public_details = json.dumps(report["details"], sort_keys=True)
    assert report["summary"]["real_doctor_probe_count"] == 1
    assert report["summary"]["installed_client_connection_acceptance_count"] == 1
    assert "opencode" not in public_details
    assert "claude-code" not in public_details
    assert ".config" not in public_details
    assert "<redacted-installed-config-target>" in public_details
    assert "<redacted-installed-client-target>" in public_details

    write_outputs(tmp_path, report, details)
    details_text = (tmp_path / "details.jsonl").read_text(encoding="utf-8")
    assert "opencode" not in details_text
    assert "claude-code" not in details_text
    assert ".config" not in details_text


def test_public_payload_sanitizer_redacts_paths_and_raw_client_output() -> None:
    """Public MCP artifacts keep status evidence without leaking local paths."""
    home = str(Path.home())
    payload = {
        "command": f"{home}/project/.venv/bin/python -m lerim.mcp_server",
        "doctor": {"config_path": f"{home}/.codex/config.toml"},
        "stdout": f"command: {home}/project/.venv/bin/python",
        "stderr": "",
    }

    sanitized = _sanitize_public_payload(payload)

    assert home not in json.dumps(sanitized)
    assert sanitized["stdout"].startswith("<redacted")
    assert sanitized["stderr"] == ""
