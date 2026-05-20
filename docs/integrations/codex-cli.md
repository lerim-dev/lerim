# Codex CLI

Codex CLI has a native Lerim adapter and an MCP config writer.

| Field | Status |
| --- | --- |
| Native trace ingestion | Yes |
| MCP config support | Yes |
| Config command | `lerim connect codex --mode mcp` |
| MCP config path | `~/.codex/config.toml` |

## What Works Today

The native adapter reads Codex JSONL sessions and prefers visible event messages when building traces for Lerim's compiler.

The MCP config writer adds Lerim to Codex CLI's MCP server config:

```bash
lerim connect codex --mode mcp --dry-run
lerim connect codex --mode mcp
```

## Current Boundary

The MCP path has stdio probe coverage. Targeted `lerim ingest --run-id ...`
is implemented and unit-covered for sessions the general background index has
not seen yet. A checked-in public current-client acceptance artifact is still
pending.

The session-finished hook is not shipped yet. Lerim should only claim automatic
Codex completed-session capture after a stable Codex completion trigger calls
that targeted ingest path.

MCP config support is not the same as native trace ingestion.

## Related

- [Integration matrix](matrix.md)
- [Integration Verification](verification.md)
- [Trace Sources, MCP Clients, And Workflow Adapters](../concepts/supported-agents.md)
- [lerim connect](../cli/connect.md)
