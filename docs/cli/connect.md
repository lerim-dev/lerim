# lerim connect

Manage native trace adapters and MCP client configuration.

## Overview

`lerim connect` has four modes:

- `--mode adapter` registers local session stores for native trace ingestion.
- `--mode mcp` writes Lerim's MCP server config into external agent clients.
- `--mode auto` tries both native adapter and MCP setup for the requested target.
- `--mode plugin` reports planned native plugin support; it does not install MCP.

Adapter mode feeds completed sessions into Lerim's compiler. MCP mode lets compatible agents query Lerim context and submit completed sessions. Auto mode reports both paths in one command. Plugin mode is currently an honest pending status for OpenClaw, Hermes, and pi.

## Syntax

```bash
lerim connect list
lerim connect list --all
lerim connect auto
lerim connect auto --mode mcp
lerim connect auto --mode auto
lerim connect <platform> [--path PATH]
lerim connect <agent> --mode mcp [--dry-run] [--force]
lerim connect <agent> --mode auto [--dry-run] [--force]
lerim connect <openclaw|hermes|pi> --mode plugin
lerim connect doctor <agent>
lerim connect remove <platform>
```

## Native Adapter Mode

Current native trace-source platforms:

```bash
lerim connect claude
lerim connect codex
lerim connect cursor
lerim connect opencode
lerim connect pi
```

Auto-detect installed native adapters:

```bash
lerim connect auto
```

Connect with a custom path:

```bash
lerim connect claude --path /custom/path/to/claude/sessions
lerim connect cursor --path ~/my-cursor-data/globalStorage
```

The path is expanded (`~` is resolved) and must exist on disk.

## MCP Mode

Install Lerim into an MCP client:

```bash
lerim connect gemini-cli --mode mcp --dry-run
lerim connect gemini-cli --mode mcp
```

For Gemini CLI specifically, `gemini mcp add` is also supported by the client:

```bash
gemini mcp add lerim "$(python -c 'import sys; print(sys.executable)')" -m lerim.mcp_server --scope user
gemini mcp list
```

The Lerim command is still the default documented path because it can dry-run,
create backups, and verify the target config.

Auto-connect detected MCP targets:

```bash
lerim connect auto --mode mcp --dry-run
lerim connect auto --mode mcp
```

Every real config write creates a timestamped backup when the target file already exists.

Supported MCP targets:

| Target | Command |
| --- | --- |
| Codex CLI | `lerim connect codex --mode mcp` |
| Claude Code | `lerim connect claude-code --mode mcp` |
| Cursor | `lerim connect cursor --mode mcp` |
| OpenCode | `lerim connect opencode --mode mcp` |
| Gemini CLI | `lerim connect gemini-cli --mode mcp` |
| Cline VS Code | `lerim connect cline --mode mcp` |
| Cline CLI | `lerim connect cline-cli --mode mcp` |
| Claude Desktop | `lerim connect claude-desktop --mode mcp` |
| OpenClaw | `lerim connect openclaw --mode mcp` |
| Hermes | `lerim connect hermes --mode mcp` |
| Goose | `lerim connect goose --mode mcp` |
| Roo Code | `lerim connect roo-code --mode mcp` |
| Kilo Code | `lerim connect kilo-code --mode mcp` |
| Windsurf | `lerim connect windsurf --mode mcp` |
| OpenHuman | `lerim connect openhuman --mode mcp` |

## Auto Mode

Auto mode composes the available paths for a target:

```bash
lerim connect codex --mode auto
lerim connect auto --mode auto --dry-run
```

For native adapters, auto mode connects when the adapter's default path or custom `--path` exists. For MCP, target-specific auto mode writes the known target config, while `lerim connect auto --mode auto` writes MCP config only for detected installed targets. The output includes separate native adapter and MCP target sections.

## Plugin And Extension Mode

Native plugin or extension support is planned but not implemented yet for:

```bash
lerim connect openclaw --mode plugin
lerim connect hermes --mode plugin
lerim connect pi --mode plugin
```

These commands return a pending/nonzero status and do not fall back to MCP. Use `--mode mcp` for current OpenClaw/Hermes MCP support. Use `lerim connect pi` for current pi native session ingestion.

## Diagnostics

List native and MCP status together:

```bash
lerim connect list --all
lerim connect list --all --json
```

Check one MCP target:

```bash
lerim connect doctor codex
lerim connect doctor hermes --json
```

## Parameters

<div class="param-field">
  <div class="param-header">
    <span class="param-name">platform_name</span>
    <span class="param-type">string</span>
    <span class="param-badge default">optional</span>
  </div>
  <p class="param-desc">Action or target: <code>list</code>, <code>auto</code>, <code>doctor</code>, <code>remove</code>, a native platform name, or an MCP target name.</p>
</div>

<div class="param-field">
  <div class="param-header">
    <span class="param-name">--mode</span>
    <span class="param-type">adapter | mcp | auto | plugin</span>
  </div>
  <p class="param-desc">Connection mode. Defaults to <code>adapter</code>. <code>auto</code> tries native adapter and MCP setup; <code>plugin</code> reports planned plugin support without installing MCP.</p>
</div>

<div class="param-field">
  <div class="param-header">
    <span class="param-name">--path</span>
    <span class="param-type">string</span>
  </div>
  <p class="param-desc">Custom filesystem path to a native adapter's session store. Overrides auto-detected default.</p>
</div>

<div class="param-field">
  <div class="param-header">
    <span class="param-name">--dry-run</span>
    <span class="param-type">boolean</span>
  </div>
  <p class="param-desc">Preview config changes without writing files. In <code>--mode auto</code>, this also previews native adapter registration.</p>
</div>

<div class="param-field">
  <div class="param-header">
    <span class="param-name">--force</span>
    <span class="param-type">boolean</span>
  </div>
  <p class="param-desc">Rewrite an existing Lerim MCP entry.</p>
</div>

## Default Native Session Paths

| Platform | Default path |
|----------|-------------|
| `claude` | `~/.claude/projects/` |
| `codex` | `~/.codex/sessions/` |
| `cursor` | `~/Library/Application Support/Cursor/User/globalStorage/` on macOS |
| `opencode` | `~/.local/share/opencode/` |
| `pi` | `~/.pi/agent/sessions/` |

## Related Commands

<div class="grid cards" markdown>

-   :material-play-circle: **lerim init**

    ---

    Interactive setup wizard

    [:octicons-arrow-right-24: lerim init](init.md)

-   :material-ingest: **lerim ingest**

    ---

    Ingest sessions after connecting

    [:octicons-arrow-right-24: lerim ingest](ingest.md)

</div>
