"""Generate the public support-boundary SVG from integration artifacts."""

from __future__ import annotations

import argparse
import html
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from lerim.adapters.registry import KNOWN_PLATFORMS
from lerim.integrations.mcp_connect import known_mcp_targets


DEFAULT_OUTPUT = Path("docs/assets/support-boundary.svg")

ADAPTER_DISPLAY_NAMES = {
    "claude": "Claude Code",
    "codex": "Codex CLI",
    "cursor": "Cursor",
    "opencode": "OpenCode",
    "pi": "pi",
}


@dataclass(frozen=True)
class SupportBoundarySnapshot:
    """Public support-boundary counts and labels."""

    native_adapter_names: tuple[str, ...]
    mcp_config_passed: int
    mcp_config_total: int
    mcp_display_names: tuple[str, ...]
    installed_client_connections: int
    gemini_live_tool_calls: int
    trace_submit_extraction_acceptances: int


def _load_report(raw_dir: Path, name: str) -> dict[str, Any]:
    """Load one raw public integration report."""
    path = raw_dir / name / "report.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _summary(report: dict[str, Any]) -> dict[str, Any]:
    """Return a report summary object, failing when the artifact is malformed."""
    summary = report.get("summary")
    if not isinstance(summary, dict):
        raise ValueError("integration report is missing a summary object")
    return summary


def _display_adapter_names() -> tuple[str, ...]:
    """Return native adapter display names from the adapter registry."""
    return tuple(
        ADAPTER_DISPLAY_NAMES.get(name, name)
        for name in KNOWN_PLATFORMS
    )


def _display_mcp_names(target_names: tuple[str, ...]) -> tuple[str, ...]:
    """Return MCP display names from the integration target registry."""
    names = set(target_names)
    ordered = tuple(
        target.display_name for target in known_mcp_targets() if target.name in names
    )
    extras = tuple(sorted(names - {target.name for target in known_mcp_targets()}))
    return ordered + extras


def _line_chunks(items: tuple[str, ...], sizes: tuple[int, ...]) -> tuple[str, ...]:
    """Return comma-separated text lines with stable item grouping."""
    lines: list[str] = []
    cursor = 0
    for size in sizes:
        chunk = items[cursor : cursor + size]
        if chunk:
            lines.append(", ".join(chunk))
        cursor += size
    if cursor < len(items):
        lines.append(", ".join(items[cursor:]))
    return tuple(lines)


def _mcp_example_lines(names: tuple[str, ...]) -> tuple[str, str]:
    """Return compact MCP example lines for the support-boundary card."""
    first_line = ", ".join(names[:3])
    remaining_count = max(0, len(names) - 5)
    second_items = list(names[3:5])
    if remaining_count:
        second_items.append(f"plus {remaining_count} more")
    return first_line, ", ".join(second_items)


def load_snapshot(raw_dir: Path) -> SupportBoundarySnapshot:
    """Build the support-boundary snapshot from raw integration reports."""
    integration = _summary(_load_report(raw_dir, "mcp-integration-full"))
    gemini = _summary(_load_report(raw_dir, "mcp-gemini-live-tool-call"))
    known_targets = tuple(str(name) for name in integration["known_targets"])
    return SupportBoundarySnapshot(
        native_adapter_names=_display_adapter_names(),
        mcp_config_passed=int(integration["config_passed_count"]),
        mcp_config_total=int(integration["known_target_count"]),
        mcp_display_names=_display_mcp_names(known_targets),
        installed_client_connections=int(
            integration["installed_client_connection_acceptance_count"]
        ),
        gemini_live_tool_calls=int(gemini["installed_client_tool_call_acceptance_count"]),
        trace_submit_extraction_acceptances=int(
            integration["trace_submit_extraction_acceptance_count"]
        ),
    )


def _text_line(
    *,
    x: int,
    y: int,
    size: int,
    fill: str,
    text: str,
    weight: int | None = None,
) -> str:
    """Render one escaped SVG text line."""
    weight_attr = f' font-weight="{weight}"' if weight is not None else ""
    return (
        f'<text x="{x}" y="{y}" font-family="Arial, Helvetica, sans-serif" '
        f'font-size="{size}"{weight_attr} fill="{fill}">{html.escape(text)}</text>'
    )


def build_svg(snapshot: SupportBoundarySnapshot) -> str:
    """Render the support-boundary SVG."""
    adapter_lines = _line_chunks(snapshot.native_adapter_names, (2, 3))
    mcp_lines = _mcp_example_lines(snapshot.mcp_display_names)
    config_label = (
        f"{snapshot.mcp_config_passed}/{snapshot.mcp_config_total} config targets"
    )
    gemini_label = (
        f"Gemini CLI has {snapshot.gemini_live_tool_calls} context-tool acceptance."
    )
    trace_label = (
        f"{snapshot.trace_submit_extraction_acceptances} synthetic extraction acceptance"
        if snapshot.trace_submit_extraction_acceptances == 1
        else f"{snapshot.trace_submit_extraction_acceptances} synthetic extraction acceptances"
    )
    footer_one = (
        f"Current public evidence: {len(snapshot.native_adapter_names)} native adapters from the registry, "
        f"{config_label}, local MCP protocol probes,"
    )
    footer_two = (
        f"{snapshot.installed_client_connections} anonymized client-connection "
        f"checks, and {snapshot.gemini_live_tool_calls} Gemini CLI "
        "context-tool acceptance."
    )

    lines = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1400" height="920" '
        'viewBox="0 0 1400 920" role="img" aria-labelledby="title desc">',
        "  <title id=\"title\">Agent integration boundary</title>",
        (
            '  <desc id="desc">A visual support boundary separating native trace '
            "ingestion, MCP context recall, MCP trace submit or import, and planned "
            "plugin or extension paths.</desc>"
        ),
        '  <rect width="1400" height="920" fill="#f5f8f5"/>',
        '  <rect x="56" y="52" width="1288" height="816" rx="18" fill="#ffffff" stroke="#d9e5dd" stroke-width="2"/>',
        "",
        "  "
        + _text_line(
            x=100,
            y=122,
            size=40,
            weight=700,
            fill="#17382a",
            text="Agent integration boundary",
        ),
        "  "
        + _text_line(
            x=100,
            y=164,
            size=20,
            fill="#53645b",
            text="MCP recall is useful, but it is not the same as native completed-session capture.",
        ),
        "",
        '  <g transform="translate(100 216)">',
        '    <rect width="380" height="276" rx="14" fill="#f8fbf8" stroke="#bdd3c7" stroke-width="2"/>',
        '    <circle cx="42" cy="46" r="14" fill="#245f46"/>',
        "    "
        + _text_line(
            x=68,
            y=54,
            size=24,
            weight=700,
            fill="#17382a",
            text="Native trace ingestion",
        ),
        "    "
        + _text_line(
            x=28,
            y=92,
            size=17,
            fill="#53645b",
            text="Reads completed local sessions and feeds",
        ),
        "    "
        + _text_line(
            x=28,
            y=116,
            size=17,
            fill="#53645b",
            text="Lerim's compiler.",
        ),
        "    "
        + _text_line(
            x=28,
            y=156,
            size=20,
            weight=700,
            fill="#17382a",
            text="Implemented adapters",
        ),
        "    "
        + _text_line(x=28, y=192, size=18, fill="#17382a", text=adapter_lines[0]),
        "    "
        + _text_line(x=28, y=224, size=18, fill="#17382a", text=adapter_lines[1]),
        "    "
        + _text_line(
            x=28,
            y=256,
            size=15,
            fill="#6a7b72",
            text="Adapter does not imply a session-end hook.",
        ),
        "  </g>",
        "",
        '  <g transform="translate(510 216)">',
        '    <rect width="380" height="276" rx="14" fill="#f8fbf8" stroke="#bdd3c7" stroke-width="2"/>',
        '    <circle cx="42" cy="46" r="14" fill="#5aa17a"/>',
        "    "
        + _text_line(
            x=68,
            y=54,
            size=24,
            weight=700,
            fill="#17382a",
            text="MCP context recall",
        ),
        "    "
        + _text_line(
            x=28,
            y=92,
            size=17,
            fill="#53645b",
            text="Lets compatible agents query context",
        ),
        "    "
        + _text_line(
            x=28,
            y=116,
            size=17,
            fill="#53645b",
            text="tools through the MCP server.",
        ),
        "    "
        + _text_line(
            x=28,
            y=156,
            size=20,
            weight=700,
            fill="#17382a",
            text=config_label,
        ),
        "    " + _text_line(x=28, y=192, size=18, fill="#17382a", text=mcp_lines[0]),
        "    " + _text_line(x=28, y=224, size=18, fill="#17382a", text=mcp_lines[1]),
        "    "
        + _text_line(
            x=28,
            y=256,
            size=15,
            fill="#6a7b72",
            text=gemini_label,
        ),
        "  </g>",
        "",
        '  <g transform="translate(920 216)">',
        '    <rect width="380" height="276" rx="14" fill="#f8fbf8" stroke="#bdd3c7" stroke-width="2"/>',
        '    <circle cx="42" cy="46" r="14" fill="#d39a3b"/>',
        "    "
        + _text_line(
            x=68,
            y=54,
            size=24,
            weight=700,
            fill="#17382a",
            text="MCP trace submit / import",
        ),
        "    "
        + _text_line(
            x=28,
            y=92,
            size=17,
            fill="#53645b",
            text="Completed traces can be submitted",
        ),
        "    "
        + _text_line(
            x=28,
            y=116,
            size=17,
            fill="#53645b",
            text="by CLI, JSONL import, or MCP.",
        ),
        "    "
        + _text_line(
            x=28,
            y=156,
            size=20,
            weight=700,
            fill="#17382a",
            text="Supported path",
        ),
        "    "
        + _text_line(x=28, y=192, size=18, fill="#17382a", text="lerim trace import"),
        "    "
        + _text_line(x=28, y=224, size=18, fill="#17382a", text="lerim_trace_submit"),
        "    "
        + _text_line(x=28, y=256, size=15, fill="#6a7b72", text=trace_label),
        "  </g>",
        "",
        '  <g transform="translate(100 536)">',
        '    <rect width="586" height="176" rx="14" fill="#fff9ed" stroke="#ead5ab" stroke-width="2"/>',
        "    "
        + _text_line(
            x=28,
            y=48,
            size=24,
            weight=700,
            fill="#17382a",
            text="Plugin or extension planned",
        ),
        "    "
        + _text_line(
            x=28,
            y=86,
            size=18,
            fill="#53645b",
            text="OpenClaw plugin, Hermes provider plugin,",
        ),
        "    "
        + _text_line(
            x=28,
            y=112,
            size=18,
            fill="#53645b",
            text="and pi extension are planned capture paths.",
        ),
        "    "
        + _text_line(
            x=28,
            y=144,
            size=16,
            fill="#6a7b72",
            text="They are not shipped as lifecycle capture yet.",
        ),
        "  </g>",
        "",
        '  <g transform="translate(714 536)">',
        '    <rect width="586" height="176" rx="14" fill="#eef6f2" stroke="#bdd3c7" stroke-width="2"/>',
        "    "
        + _text_line(
            x=28,
            y=48,
            size=24,
            weight=700,
            fill="#17382a",
            text="Acceptance standard",
        ),
        "    "
        + _text_line(
            x=28,
            y=86,
            size=18,
            fill="#53645b",
            text="A broad support claim needs recall and capture",
        ),
        "    "
        + _text_line(
            x=28,
            y=112,
            size=18,
            fill="#53645b",
            text="tested against the actual client/config.",
        ),
        "    "
        + _text_line(
            x=28,
            y=138,
            size=16,
            fill="#6a7b72",
            text="Config writers are evidence, not the whole claim.",
        ),
        "  </g>",
        "",
        '  <line x1="100" y1="760" x2="1300" y2="760" stroke="#d9e5dd" stroke-width="2"/>',
        "  "
        + _text_line(x=100, y=798, size=16, fill="#6a7b72", text=footer_one),
        "  "
        + _text_line(x=100, y=828, size=16, fill="#6a7b72", text=footer_two),
        "  "
        + _text_line(
            x=100,
            y=858,
            size=16,
            fill="#6a7b72",
            text="Use the integration matrix for exact per-agent limitations before making public support claims.",
        ),
        "</svg>",
        "",
    ]
    return "\n".join(lines)


def generate(*, repo_root: Path, output: Path = DEFAULT_OUTPUT) -> Path:
    """Generate the support-boundary SVG and return the output path."""
    repo_root = repo_root.resolve()
    raw_dir = repo_root / "benchmarks" / "results" / "raw"
    output_path = output if output.is_absolute() else repo_root / output
    snapshot = load_snapshot(raw_dir)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(build_svg(snapshot), encoding="utf-8")
    return output_path


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Generate docs/assets/support-boundary.svg from raw artifacts."
    )
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    """Generate the support-boundary SVG from the command line."""
    args = parse_args()
    output_path = generate(repo_root=args.repo_root, output=args.output)
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
