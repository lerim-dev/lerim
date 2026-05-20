# Cline

Cline is currently MCP-first in Lerim. Lerim supports both the VS Code
extension settings path and the Cline CLI MCP config path.

| Field | Status |
| --- | --- |
| Native trace ingestion | No native adapter yet |
| MCP config support | Yes |
| VS Code config command | `lerim connect cline --mode mcp` |
| VS Code MCP config path | VS Code global storage `cline_mcp_settings.json` |
| CLI config command | `lerim connect cline-cli --mode mcp` |
| CLI MCP config path | `~/.cline/mcp.json` |

## What Works Today

The MCP config writers add Lerim to Cline's MCP settings.

For the VS Code extension path:

```bash
lerim connect cline --mode mcp --dry-run
lerim connect cline --mode mcp
```

For the Cline CLI path:

```bash
lerim connect cline-cli --mode mcp --dry-run
lerim connect cline-cli --mode mcp
```

This config registers Lerim's MCP tool surface for Cline. Treat live tool use
as unverified until an installed-client acceptance artifact exists.

## Current Boundary

Cline does not have native Lerim trace ingestion yet. Completed-session capture requires either a future native adapter or explicit submission through `lerim_trace_submit`.

VS Code profile and global storage paths can vary by environment. The Cline CLI
uses its own `~/.cline/mcp.json` path, so configure both if you use both
surfaces.

## Related

- [Integration matrix](matrix.md)
- [Integration Verification](verification.md)
- [Trace Sources, MCP Clients, And Workflow Adapters](../concepts/supported-agents.md)
- [lerim connect](../cli/connect.md)
