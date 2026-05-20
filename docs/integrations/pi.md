# pi

pi is supported through native session ingestion. Lerim reads completed pi JSONL
sessions and feeds them into the same trace-to-context compiler used by the
other native adapters.

| Field | Status |
| --- | --- |
| Native trace ingestion | Yes |
| Native session path | `~/.pi/agent/sessions/` |
| Config command | `lerim connect pi` |
| MCP config support | Not claimed |
| Extension support | Planned, not shipped |

## What Works Today

Connect pi's completed session store:

```bash
lerim connect pi
lerim ingest --agent pi
```

The adapter follows pi's documented session format: it keeps user, assistant,
custom context, branch-summary, and compaction-summary entries; clears bulky
tool outputs and thinking blocks; and writes compact canonical JSONL for
Lerim's compiler.

## Current Boundary

pi's public docs describe session JSONL files and TypeScript extensions. They
do not currently document a pi MCP config path, so Lerim does not expose
`lerim connect pi --mode mcp`.

`lerim connect pi --mode plugin` reports the pending extension status. A future
extension can add startup context injection or explicit lifecycle capture once
that path is implemented and tested.

## Related

- [Integration matrix](matrix.md)
- [Integration Verification](verification.md)
- [Trace Sources, MCP Clients, And Workflow Adapters](../concepts/supported-agents.md)
- [lerim connect](../cli/connect.md)
