# Claude Code

Claude Code has a native Lerim adapter and an MCP config writer.

| Field | Status |
| --- | --- |
| Native trace ingestion | Yes |
| MCP config support | Yes |
| Config command | `lerim connect claude-code --mode mcp` |
| MCP config path | `~/.claude.json` |

## What Works Today

The native adapter reads completed Claude project sessions and feeds them into Lerim's trace-to-context compiler.

The MCP config writer adds Lerim as a Claude Code MCP server for context recall and trace submission tools:

```bash
lerim connect claude-code --mode mcp --dry-run
lerim connect claude-code --mode mcp
```

## Current Boundary

The MCP path has stdio probe coverage, but a Claude Code session-end hook is not added yet. Treat MCP recall and native trace ingestion as separate paths.

Claude Code config shape can vary by version. Current local validation uses the
Claude Code CLI's user-level `mcpServers` shape in `~/.claude.json`; use
`--dry-run` before writing config on a new setup.

## Related

- [Integration matrix](matrix.md)
- [Integration Verification](verification.md)
- [Trace Sources, MCP Clients, And Workflow Adapters](../concepts/supported-agents.md)
- [lerim connect](../cli/connect.md)
