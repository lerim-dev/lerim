# Roo Code

Roo Code is currently MCP-first in Lerim.

| Field | Status |
| --- | --- |
| Native trace ingestion | No native adapter yet |
| MCP config support | Yes |
| Config command | `lerim connect roo-code --mode mcp` |
| MCP config path | VS Code global storage `mcp_settings.json` |

## What Works Today

The MCP config writer adds Lerim to Roo Code's MCP settings:

```bash
lerim connect roo-code --mode mcp --dry-run
lerim connect roo-code --mode mcp
```

This config registers Lerim's MCP tool surface for Roo Code. Treat live tool
use as unverified until an installed-client acceptance artifact exists.

## Current Boundary

Roo Code does not have native Lerim trace ingestion yet. MCP config support is recall access and optional trace submission, not a claim that Lerim captures Roo Code sessions automatically.

VS Code profile and global storage paths can vary by environment.

## Related

- [Integration matrix](matrix.md)
- [Integration Verification](verification.md)
- [Trace Sources, MCP Clients, And Workflow Adapters](../concepts/supported-agents.md)
- [lerim connect](../cli/connect.md)
