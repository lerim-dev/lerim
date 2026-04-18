# How It Works

Lerim is a DB-only context system.

## Summary

The flow is:

1. adapters read raw agent sessions
2. traces are normalized
3. `sync` extracts durable context records
4. `maintain` consolidates the record graph
5. `ask` retrieves records and answers questions

## Storage

Canonical storage is global:

- `~/.lerim/context.sqlite3` — records, versions, links, evidence, findings
- `~/.lerim/index/sessions.sqlite3` — session catalog and queue
- `~/.lerim/workspace/` — run artifacts and logs

Projects are scoped by `project_id` inside the database.

## Agent tool surface

Lerim does not expose raw SQL or file CRUD to the agent.

The durable context tools are:

- `trace_read`
- `context_search`
- `context_fetch`
- `context_apply`

The extract flow also uses:

- `note`
- `prune`

## Why this design

The agent says what it wants to do.
Python owns the storage mechanics.

That keeps:

- tool use smaller
- prompts cleaner
- invariants enforced in code
- training trajectories easier for smaller models later
