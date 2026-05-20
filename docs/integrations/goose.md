# Goose

Goose is currently MCP-first in Lerim.

| Field | Status |
| --- | --- |
| Native trace ingestion | No native adapter yet |
| MCP config support | Yes |
| Config command | `lerim connect goose --mode mcp` |
| MCP config path | `~/.config/goose/config.yaml` |

## What Works Today

The MCP config writer adds Lerim to Goose's MCP config:

```bash
lerim connect goose --mode mcp --dry-run
lerim connect goose --mode mcp
```

This config registers Lerim's MCP tool surface for Goose. Treat live tool use
as unverified until an installed-client acceptance artifact exists.

## Current Boundary

Goose does not have native Lerim trace ingestion yet. Treat the current integration as recall-first until a stable session export path is validated.

## Related

- [Integration matrix](matrix.md)
- [Integration Verification](verification.md)
- [Trace Sources, MCP Clients, And Workflow Adapters](../concepts/supported-agents.md)
- [lerim connect](../cli/connect.md)
