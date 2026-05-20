# OpenHuman

OpenHuman is currently an experimental generic MCP/manual target in Lerim.

| Field | Status |
| --- | --- |
| Native trace ingestion | Investigating |
| MCP config support | Yes |
| Config command | `lerim connect openhuman --mode mcp` |
| MCP config path | `~/.openhuman/mcp.json` |

## What Works Today

The MCP config writer adds Lerim to OpenHuman's MCP config:

```bash
lerim connect openhuman --mode mcp --dry-run
lerim connect openhuman --mode mcp
```

This config registers Lerim's MCP tool surface for OpenHuman-shaped clients.
This repo has config-writer coverage only; it does not yet have real OpenHuman
client-loading or tool-call evidence.

## Current Boundary

Do not treat OpenHuman as full native support yet. The upstream automation and memory-trait path is still unclear, so completed-session capture remains manual or future integration work.

## Related

- [Integration matrix](matrix.md)
- [Integration Verification](verification.md)
- [Trace Sources, MCP Clients, And Workflow Adapters](../concepts/supported-agents.md)
- [lerim connect](../cli/connect.md)
