# Claude Desktop

Claude Desktop is currently MCP-first in Lerim.

| Field | Status |
| --- | --- |
| Native trace ingestion | No native adapter yet |
| MCP config support | Yes |
| Config command | `lerim connect claude-desktop --mode mcp` |
| MCP config path | Claude Desktop config JSON |

## What Works Today

The MCP config writer adds Lerim to Claude Desktop's MCP config:

```bash
lerim connect claude-desktop --mode mcp --dry-run
lerim connect claude-desktop --mode mcp
```

This config registers Lerim's MCP tool surface for Claude Desktop. Treat live
tool use as unverified until an installed-client acceptance artifact exists.

## Current Boundary

Claude Desktop does not have native Lerim trace ingestion yet. Treat the current integration as desktop recall only; Lerim does not claim automatic completed-session capture from Claude Desktop.

## Related

- [Integration matrix](matrix.md)
- [Integration Verification](verification.md)
- [Trace Sources, MCP Clients, And Workflow Adapters](../concepts/supported-agents.md)
- [lerim connect](../cli/connect.md)
