# Cursor

Cursor has a native Lerim adapter and an MCP config writer.

| Field | Status |
| --- | --- |
| Native trace ingestion | Yes |
| MCP config support | Yes |
| Config command | `lerim connect cursor --mode mcp` |
| MCP config path | `~/.cursor/mcp.json` |

## What Works Today

The native adapter reads Cursor's local storage and exports compact traces for Lerim's compiler.

The MCP config writer adds Lerim to Cursor's MCP config:

```bash
lerim connect cursor --mode mcp --dry-run
lerim connect cursor --mode mcp
```

## Current Boundary

Cursor local storage and database formats can change. Lerim's support boundary is the current adapter plus MCP config writer, not a promise that every future Cursor storage shape is accepted without validation.

## Related

- [Integration matrix](matrix.md)
- [Integration Verification](verification.md)
- [Trace Sources, MCP Clients, And Workflow Adapters](../concepts/supported-agents.md)
- [lerim connect](../cli/connect.md)

