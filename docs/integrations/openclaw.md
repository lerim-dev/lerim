# OpenClaw

OpenClaw is currently MCP-first in Lerim, with native plugin support planned.

| Field | Status |
| --- | --- |
| Native trace ingestion | Planned plugin, not shipped |
| MCP config support | Yes |
| Config command | `lerim connect openclaw --mode mcp` |
| MCP config path | `~/.openclaw/openclaw.json` |

## What Works Today

The MCP config writer adds Lerim to OpenClaw's MCP config:

```bash
lerim connect openclaw --mode mcp --dry-run
lerim connect openclaw --mode mcp
```

Lerim writes OpenClaw's documented nested registry shape:

```json
{
  "mcp": {
    "servers": {
      "lerim": {
        "command": "/absolute/path/to/python",
        "args": ["-m", "lerim.mcp_server"]
      }
    }
  }
}
```

This config registers Lerim's MCP tool surface for OpenClaw. Treat live tool
use as unverified until an installed-client acceptance artifact exists.

## Current Boundary

The native OpenClaw plugin is planned, not shipped. Do not treat MCP config support as native lifecycle capture.

`lerim connect openclaw --mode plugin` reports the pending plugin status and does not install MCP.

## Related

- [Integration matrix](matrix.md)
- [Integration Verification](verification.md)
- [Trace Sources, MCP Clients, And Workflow Adapters](../concepts/supported-agents.md)
- [lerim connect](../cli/connect.md)
- [OpenClaw MCP docs](https://docs.openclaw.ai/cli/mcp)
