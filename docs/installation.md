# Installation

Install Lerim, connect current trace sources, and start the service.

## Install

```bash
pip install lerim
```

## Initialize

```bash
lerim init
```

This writes user config to the active Lerim config path (by default `~/.lerim/config.toml`).

## Connect current trace sources

```bash
lerim connect auto
```

Or connect one native source-session adapter manually:

```bash
lerim connect claude
lerim connect codex
```

The first native adapters are strongest for coding-agent session stores. For
support, incident, research, or other business workflows, use custom trace
folders or MCP `lerim_trace_submit`.

## Connect MCP clients

For agents that support MCP, install Lerim as their shared context server:

```bash
lerim connect auto --mode mcp --dry-run
lerim connect auto --mode mcp
```

Use `--dry-run` first to preview the real config files Lerim will edit. Every
write creates a timestamped backup when a target config already exists.

## Register a project

```bash
lerim project add .
```

This only registers the repo path.

## Start Lerim

```bash
lerim up
```

Or run the server directly:

```bash
lerim serve
```

If you run `lerim serve` directly instead of `lerim up`, restart it after
changing registered projects or config that affects scope or runtime mounts.
