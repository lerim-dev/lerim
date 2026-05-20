"""MCP client configuration support for external agent tools."""

from __future__ import annotations

import json
import shutil
import sys
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import json5
import tomlkit
import yaml


ConfigFormat = Literal[
    "json_claude_code",
    "json_mcp_servers",
    "json_mcp_nested_servers",
    "json_opencode",
    "yaml_mcp_servers",
    "toml_mcp_servers",
]


@dataclass(frozen=True)
class McpTarget:
    """One supported MCP client configuration target."""

    name: str
    display_name: str
    config_path: Path
    config_format: ConfigFormat
    aliases: tuple[str, ...] = ()
    detect_paths: tuple[Path, ...] = ()
    docs_url: str = ""


@dataclass(frozen=True)
class McpConnectResult:
    """Result of installing or checking one MCP client config."""

    name: str
    display_name: str
    config_path: str
    status: str
    installed: bool
    already_configured: bool
    dry_run: bool
    backup_path: str | None = None
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe result payload."""
        return {
            "name": self.name,
            "display_name": self.display_name,
            "config_path": self.config_path,
            "status": self.status,
            "installed": self.installed,
            "already_configured": self.already_configured,
            "dry_run": self.dry_run,
            "backup_path": self.backup_path,
            "message": self.message,
        }


def known_mcp_targets() -> tuple[McpTarget, ...]:
    """Return Lerim's known first-batch and second-batch MCP targets."""
    home = Path.home()
    return (
        McpTarget(
            name="codex",
            display_name="Codex CLI",
            config_path=home / ".codex" / "config.toml",
            config_format="toml_mcp_servers",
            aliases=("codex-cli",),
            detect_paths=(home / ".codex",),
            docs_url="https://developers.openai.com/codex",
        ),
        McpTarget(
            name="claude-code",
            display_name="Claude Code",
            config_path=home / ".claude.json",
            config_format="json_claude_code",
            aliases=("claude",),
            detect_paths=(home / ".claude", home / ".claude.json"),
            docs_url="https://docs.anthropic.com/en/docs/claude-code",
        ),
        McpTarget(
            name="cursor",
            display_name="Cursor",
            config_path=home / ".cursor" / "mcp.json",
            config_format="json_mcp_servers",
            aliases=("cursor-agent",),
            detect_paths=(
                home / ".cursor",
                home / "Library" / "Application Support" / "Cursor",
            ),
            docs_url="https://docs.cursor.com/tools/mcp",
        ),
        McpTarget(
            name="opencode",
            display_name="OpenCode",
            config_path=home / ".config" / "opencode" / "opencode.json",
            config_format="json_opencode",
            aliases=("opencode-ai",),
            detect_paths=(
                home / ".config" / "opencode",
                home / ".local" / "share" / "opencode",
            ),
            docs_url="https://opencode.ai/docs/mcp-servers/",
        ),
        McpTarget(
            name="gemini-cli",
            display_name="Gemini CLI",
            config_path=home / ".gemini" / "settings.json",
            config_format="json_mcp_servers",
            aliases=("gemini",),
            detect_paths=(home / ".gemini",),
            docs_url="https://github.com/google-gemini/gemini-cli/blob/main/docs/tools/mcp-server.md",
        ),
        McpTarget(
            name="cline",
            display_name="Cline VS Code",
            config_path=(
                home
                / "Library"
                / "Application Support"
                / "Code"
                / "User"
                / "globalStorage"
                / "saoudrizwan.claude-dev"
                / "settings"
                / "cline_mcp_settings.json"
            ),
            config_format="json_mcp_servers",
            aliases=("cline-vscode",),
            detect_paths=(
                home / "Library" / "Application Support" / "Code",
                home / ".config" / "Code",
            ),
            docs_url="https://docs.cline.bot/mcp/configuring-mcp-servers",
        ),
        McpTarget(
            name="cline-cli",
            display_name="Cline CLI",
            config_path=home / ".cline" / "mcp.json",
            config_format="json_mcp_servers",
            aliases=("cline-terminal",),
            detect_paths=(home / ".cline",),
            docs_url="https://docs.cline.bot/mcp/configuring-mcp-servers",
        ),
        McpTarget(
            name="claude-desktop",
            display_name="Claude Desktop",
            config_path=(
                home
                / "Library"
                / "Application Support"
                / "Claude"
                / "claude_desktop_config.json"
            ),
            config_format="json_mcp_servers",
            aliases=("claude-desktop-app",),
            detect_paths=(home / "Library" / "Application Support" / "Claude",),
            docs_url="https://modelcontextprotocol.io/quickstart/user",
        ),
        McpTarget(
            name="openclaw",
            display_name="OpenClaw",
            config_path=home / ".openclaw" / "openclaw.json",
            config_format="json_mcp_nested_servers",
            aliases=("open-claw",),
            detect_paths=(home / ".openclaw",),
            docs_url="https://docs.openclaw.ai/cli/mcp",
        ),
        McpTarget(
            name="hermes",
            display_name="Hermes",
            config_path=home / ".hermes" / "config.yaml",
            config_format="yaml_mcp_servers",
            aliases=("hermes-agent",),
            detect_paths=(home / ".hermes",),
            docs_url="https://docs.opencomputer.dev/agents/cores/hermes",
        ),
        McpTarget(
            name="goose",
            display_name="Goose",
            config_path=home / ".config" / "goose" / "config.yaml",
            config_format="yaml_mcp_servers",
            detect_paths=(home / ".config" / "goose",),
            docs_url="https://block.github.io/goose/",
        ),
        McpTarget(
            name="roo-code",
            display_name="Roo Code",
            config_path=(
                home
                / "Library"
                / "Application Support"
                / "Code"
                / "User"
                / "globalStorage"
                / "rooveterinaryinc.roo-cline"
                / "settings"
                / "mcp_settings.json"
            ),
            config_format="json_mcp_servers",
            aliases=("roo",),
            detect_paths=(home / "Library" / "Application Support" / "Code",),
            docs_url="https://docs.roocode.com/features/mcp/using-mcp-in-roo",
        ),
        McpTarget(
            name="kilo-code",
            display_name="Kilo Code",
            config_path=(
                home
                / "Library"
                / "Application Support"
                / "Code"
                / "User"
                / "globalStorage"
                / "kilocode.kilo-code"
                / "settings"
                / "mcp_settings.json"
            ),
            config_format="json_mcp_servers",
            aliases=("kilo",),
            detect_paths=(home / "Library" / "Application Support" / "Code",),
            docs_url="https://kilocode.ai/docs/features/mcp/using-mcp-in-kilo-code",
        ),
        McpTarget(
            name="windsurf",
            display_name="Windsurf",
            config_path=home / ".codeium" / "windsurf" / "mcp_config.json",
            config_format="json_mcp_servers",
            detect_paths=(home / ".codeium" / "windsurf",),
            docs_url="https://docs.windsurf.com/windsurf/cascade/mcp",
        ),
        McpTarget(
            name="openhuman",
            display_name="OpenHuman",
            config_path=home / ".openhuman" / "mcp.json",
            config_format="json_mcp_servers",
            detect_paths=(home / ".openhuman",),
            docs_url="https://github.com/tinyhumansai/openhuman",
        ),
    )


def resolve_mcp_target(name: str) -> McpTarget | None:
    """Resolve a target name or alias."""
    normalized = _normalize_target_name(name)
    for target in known_mcp_targets():
        names = {target.name, *target.aliases}
        if normalized in {_normalize_target_name(item) for item in names}:
            return target
    return None


def installed_mcp_targets() -> list[McpTarget]:
    """Return targets whose config or detection directories are present."""
    targets: list[McpTarget] = []
    for target in known_mcp_targets():
        if target.config_path.exists() or any(path.exists() for path in target.detect_paths):
            targets.append(target)
    return targets


def connect_mcp_target(
    target: McpTarget,
    *,
    dry_run: bool = False,
    force: bool = False,
) -> McpConnectResult:
    """Install Lerim's MCP server into one target config."""
    existing = _read_config(target)
    updated, changed = _with_lerim_entry(existing, target)
    already = not changed
    if already and not force:
        return McpConnectResult(
            name=target.name,
            display_name=target.display_name,
            config_path=str(target.config_path),
            status="already_configured",
            installed=True,
            already_configured=True,
            dry_run=dry_run,
            message="Lerim MCP entry already exists.",
        )
    if dry_run:
        return McpConnectResult(
            name=target.name,
            display_name=target.display_name,
            config_path=str(target.config_path),
            status="would_update" if target.config_path.exists() else "would_create",
            installed=False,
            already_configured=already,
            dry_run=True,
            message="Dry run only. No file was written.",
        )
    backup_path = _backup_config(target.config_path) if target.config_path.exists() else None
    _write_config(target, updated)
    verified, _changed_after_verify = _with_lerim_entry(_read_config(target), target)
    if verified != updated:
        return McpConnectResult(
            name=target.name,
            display_name=target.display_name,
            config_path=str(target.config_path),
            status="verification_failed",
            installed=False,
            already_configured=already,
            dry_run=False,
            backup_path=str(backup_path) if backup_path else None,
            message="Config write completed but verification did not match.",
        )
    return McpConnectResult(
        name=target.name,
        display_name=target.display_name,
        config_path=str(target.config_path),
        status="installed" if not already else "updated",
        installed=True,
        already_configured=already,
        dry_run=False,
        backup_path=str(backup_path) if backup_path else None,
        message="Lerim MCP entry installed.",
    )


def doctor_mcp_target(target: McpTarget) -> dict[str, Any]:
    """Return read-only MCP config status for one target."""
    try:
        data = _read_config(target)
        _updated, changed = _with_lerim_entry(data, target)
        parse_error = ""
    except Exception as exc:
        changed = True
        parse_error = f"{type(exc).__name__}: {exc}"
    return {
        "name": target.name,
        "display_name": target.display_name,
        "config_path": str(target.config_path),
        "config_exists": target.config_path.exists(),
        "detected": target.config_path.exists()
        or any(path.exists() for path in target.detect_paths),
        "configured": not changed,
        "parse_error": parse_error,
        "docs_url": target.docs_url,
    }


def lerim_mcp_command() -> dict[str, Any]:
    """Return the standard command object for JSON-like MCP configs."""
    return {"command": sys.executable, "args": ["-m", "lerim.mcp_server"]}


def _with_lerim_entry(data: dict[str, Any], target: McpTarget) -> tuple[dict[str, Any], bool]:
    """Return config data with the Lerim MCP entry and whether it changed."""
    original = _config_signature(data, target)
    updated: dict[str, Any] = deepcopy(data)
    if target.config_format == "json_mcp_nested_servers":
        mcp_block = dict(updated.get("mcp") or {})
        servers = dict(mcp_block.get("servers") or {})
        servers["lerim"] = lerim_mcp_command()
        mcp_block["servers"] = servers
        updated["mcp"] = mcp_block
    elif target.config_format == "json_claude_code":
        servers = dict(updated.get("mcpServers") or {})
        servers["lerim"] = {
            "type": "stdio",
            "command": sys.executable,
            "args": ["-m", "lerim.mcp_server"],
            "env": {},
        }
        updated["mcpServers"] = servers
    elif target.config_format == "json_opencode":
        servers = dict(updated.get("mcp") or {})
        servers["lerim"] = {
            "type": "local",
            "command": [sys.executable, "-m", "lerim.mcp_server"],
            "enabled": True,
        }
        updated["mcp"] = servers
    elif target.config_format == "toml_mcp_servers":
        servers = updated.get("mcp_servers")
        if servers is None:
            servers = tomlkit.table()
            updated["mcp_servers"] = servers
        entry = tomlkit.table()
        entry["command"] = sys.executable
        entry["args"] = ["-m", "lerim.mcp_server"]
        servers["lerim"] = entry
    else:
        key = "mcp_servers" if target.config_format in {"yaml_mcp_servers", "toml_mcp_servers"} else "mcpServers"
        servers = dict(updated.get(key) or {})
        servers["lerim"] = lerim_mcp_command()
        updated[key] = servers
    changed = _config_signature(updated, target) != original
    return updated, changed


def _read_config(target: McpTarget) -> dict[str, Any]:
    """Read one target config, returning an empty object when absent."""
    path = target.config_path
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    if target.config_format == "toml_mcp_servers":
        parsed = tomlkit.parse(text)
        return parsed
    if target.config_format == "yaml_mcp_servers":
        loaded = yaml.safe_load(text) or {}
        return loaded if isinstance(loaded, dict) else {}
    if path.suffix.lower() in {".json5", ".jsonc"}:
        loaded = json5.loads(text)
    else:
        try:
            loaded = json.loads(text)
        except json.JSONDecodeError:
            loaded = json5.loads(text)
    return loaded if isinstance(loaded, dict) else {}


def _write_config(target: McpTarget, data: dict[str, Any]) -> None:
    """Write one target config in its native format."""
    target.config_path.parent.mkdir(parents=True, exist_ok=True)
    if target.config_format == "toml_mcp_servers":
        target.config_path.write_text(tomlkit.dumps(data), encoding="utf-8")
        return
    if target.config_format == "yaml_mcp_servers":
        target.config_path.write_text(
            yaml.safe_dump(data, sort_keys=False),
            encoding="utf-8",
        )
        return
    target.config_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def _backup_config(path: Path) -> Path:
    """Create a timestamped backup next to a config file."""
    suffix = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    backup = path.with_name(f"{path.name}.lerim-backup-{suffix}")
    shutil.copy2(path, backup)
    return backup


def _config_signature(data: dict[str, Any], target: McpTarget) -> str:
    """Return a stable signature for config change detection."""
    if target.config_format == "toml_mcp_servers":
        return tomlkit.dumps(data)
    return json.dumps(data, sort_keys=True, default=str)


def _normalize_target_name(name: str) -> str:
    """Normalize target names and aliases."""
    return str(name or "").strip().lower().replace("_", "-")


if __name__ == "__main__":
    """Print known targets for a quick manual smoke check."""
    for item in known_mcp_targets():
        print(f"{item.name}: {item.config_path}")
