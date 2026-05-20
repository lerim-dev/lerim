# Windsurf

Windsurf is currently MCP-first in Lerim.

| Field | Status |
| --- | --- |
| Native trace ingestion | No native adapter yet |
| MCP config support | Yes |
| Config command | `lerim connect windsurf --mode mcp` |
| MCP config path | `~/.codeium/windsurf/mcp_config.json` |

## What Works Today

The MCP config writer adds Lerim to Windsurf's MCP config:

```bash
lerim connect windsurf --mode mcp --dry-run
lerim connect windsurf --mode mcp
```

This config registers Lerim's MCP tool surface for Windsurf. Treat live tool
use as unverified until an installed-client acceptance artifact exists.

## Current Boundary

Windsurf does not have native Lerim trace ingestion yet. Treat the current integration as recall-first unless a Cascade trace export path is validated.

## Related

- [Integration matrix](matrix.md)
- [Integration Verification](verification.md)
- [Trace Sources, MCP Clients, And Workflow Adapters](../concepts/supported-agents.md)
- [lerim connect](../cli/connect.md)
