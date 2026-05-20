# OpenCode

OpenCode has a native Lerim adapter and an MCP config writer.

| Field | Status |
| --- | --- |
| Native trace ingestion | Yes |
| MCP config support | Yes |
| Config command | `lerim connect opencode --mode mcp` |
| MCP config path | `~/.config/opencode/opencode.json` |

## What Works Today

The native adapter reads OpenCode's local session store and feeds completed sessions into Lerim's compiler.

The MCP config writer adds Lerim to OpenCode's top-level `mcp` config:

```bash
lerim connect opencode --mode mcp --dry-run
lerim connect opencode --mode mcp
```

## Current Boundary

OpenCode config and data paths can differ by install. Use `--dry-run` to preview the config write, and use native adapter mode only when the local session store path is present.

## Related

- [Integration matrix](matrix.md)
- [Integration Verification](verification.md)
- [Trace Sources, MCP Clients, And Workflow Adapters](../concepts/supported-agents.md)
- [lerim connect](../cli/connect.md)

