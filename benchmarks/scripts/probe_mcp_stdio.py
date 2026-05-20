"""Probe an installed Lerim MCP stdio entrypoint."""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from datetime import timedelta
from pathlib import Path

import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


EXPECTED_TOOLS = (
    "lerim_context_brief",
    "lerim_context_answer",
    "lerim_context_search",
    "lerim_records_list",
    "lerim_trace_submit",
    "lerim_ingest_status",
)


def _toml_string(value: Path) -> str:
    """Return a small TOML string literal for a local path."""
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"') + '"'


def _write_isolated_config(root: Path) -> Path:
    """Write an isolated Lerim config for the probe process."""
    data_dir = root / "data"
    config_path = root / "config.toml"
    config_path.write_text(f"[data]\ndir = {_toml_string(data_dir)}\n", encoding="utf-8")
    return config_path


async def _probe(args: argparse.Namespace) -> None:
    """Start one MCP server process and assert that expected tools are listed."""
    with tempfile.TemporaryDirectory(prefix="lerim-mcp-probe-") as tmp:
        env = os.environ.copy()
        env["LERIM_CONFIG"] = str(_write_isolated_config(Path(tmp)))
        params = StdioServerParameters(
            command=args.command,
            args=args.arg,
            env=env,
            cwd=args.cwd,
        )
        timeout = timedelta(seconds=args.timeout_seconds)
        async with stdio_client(params) as (read_stream, write_stream):
            async with ClientSession(
                read_stream,
                write_stream,
                read_timeout_seconds=timeout,
            ) as session:
                await session.initialize()
                response = await session.list_tools()
    actual = {tool.name for tool in response.tools}
    expected = set(args.expected_tool or EXPECTED_TOOLS)
    missing = sorted(expected - actual)
    if missing:
        raise SystemExit(
            "missing expected MCP tools: "
            + ", ".join(missing)
            + f"; actual={sorted(actual)}"
        )
    print(
        "mcp_probe_ok "
        f"command={args.command!r} args={args.arg!r} tools={','.join(sorted(actual))}"
    )


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--command", required=True, help="Executable to launch.")
    parser.add_argument(
        "--arg",
        action="append",
        default=[],
        help="Argument passed to the executable. Repeat for multiple args.",
    )
    parser.add_argument(
        "--expected-tool",
        action="append",
        default=[],
        help="Expected MCP tool name. Defaults to Lerim's public tool set.",
    )
    parser.add_argument(
        "--cwd",
        default=None,
        help="Optional working directory for the MCP process.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=20.0,
        help="Read timeout for MCP initialize/list-tools calls.",
    )
    return parser.parse_args()


def main() -> int:
    """Run the probe."""
    args = parse_args()
    try:
        anyio.run(_probe, args)
    except BaseException as exc:
        print(f"mcp_probe_failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
