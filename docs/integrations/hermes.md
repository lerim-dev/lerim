# Hermes

Hermes is currently MCP-first in Lerim, with native provider plugin support planned.

| Field | Status |
| --- | --- |
| Native trace ingestion | Planned provider plugin, not shipped |
| MCP config support | Yes |
| Config command | `lerim connect hermes --mode mcp` |
| MCP config path | `~/.hermes/config.yaml` |

## What Works Today

The MCP config writer adds Lerim to Hermes' MCP config:

```bash
lerim connect hermes --mode mcp --dry-run
lerim connect hermes --mode mcp
```

This config registers Lerim's MCP tool surface for Hermes. Treat live tool use
as unverified until an installed-client acceptance artifact exists.

## Current Boundary

The native Hermes provider plugin is planned, not shipped. Do not treat MCP config support as native lifecycle capture.

`lerim connect hermes --mode plugin` reports the pending plugin status and does not install MCP.

## Related

- [Integration matrix](matrix.md)
- [Integration Verification](verification.md)
- [Trace Sources, MCP Clients, And Workflow Adapters](../concepts/supported-agents.md)
- [lerim connect](../cli/connect.md)
