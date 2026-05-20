# Gemini CLI

Gemini CLI is currently MCP-first in Lerim.

| Field | Status |
| --- | --- |
| Native trace ingestion | No native adapter yet |
| MCP config support | Yes |
| Config command | `lerim connect gemini-cli --mode mcp` |
| MCP config path | `~/.gemini/settings.json` |

## What Works Today

The MCP config writer adds Lerim as a Gemini CLI MCP server:

```bash
lerim connect gemini-cli --mode mcp --dry-run
lerim connect gemini-cli --mode mcp
```

The Lerim MCP server exposes context-recall and trace-submission tools through
that config. Current public installed-client evidence proves a Gemini
`lerim_context_brief` call; it does not claim an installed Gemini
`lerim_trace_submit` call yet.

A live Gemini CLI acceptance artifact currently records that Gemini can call
Lerim's `lerim_context_brief` MCP tool in this environment. See
[MCP Integration](../benchmarks/lerim-results.md#mcp-integration) for the
current public evidence boundary and raw artifact.

Gemini CLI also exposes its own MCP installer:

```bash
gemini mcp add lerim "$(python -c 'import sys; print(sys.executable)')" -m lerim.mcp_server --scope user
gemini mcp list
```

Use `lerim connect gemini-cli --mode mcp` when you want Lerim to write and
verify the config with dry-run and backup behavior. Use `gemini mcp add` when
you prefer Gemini CLI's own config command or need a project-scoped entry.

## Current Boundary

Gemini CLI does not have a native Lerim trace adapter yet. Treat the current
integration as MCP context recall plus user- or client-invoked trace submission
through Lerim's tool surface until a stable completed-session export or capture
path is validated.

## Related

- [Integration matrix](matrix.md)
- [Integration Verification](verification.md)
- [Trace Sources, MCP Clients, And Workflow Adapters](../concepts/supported-agents.md)
- [lerim connect](../cli/connect.md)
