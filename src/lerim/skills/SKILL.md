---
name: lerim
description: Persistent memory for coding agents. Query past decisions and learnings before starting work. Lerim watches your sessions, extracts what matters, and makes it available across every future session.
---

# Lerim

Lerim gives you persistent memory across sessions. It watches your conversations, extracts decisions and learnings, and stores them in the global context database at `~/.lerim/context.sqlite3`.
Hybrid retrieval is local: ONNX embeddings from `mixedbread-ai/mxbai-embed-xsmall-v1`, `sqlite-vec` vector search, SQLite FTS5, and RRF fusion.

## Start here

At the beginning of each session, query Lerim instead of manually browsing stored context.
Use `lerim ask` for synthesized answers or `lerim status --json` to inspect the system state.
The durable source of truth is the SQLite context DB, not project-local memory folders.

## When to use

- **Before starting a task**: query Lerim for relevant project context.
- **When making a decision**: check if a similar decision was already made.
- **When debugging**: look up past learnings about the area you're working in.

## Commands

```bash
lerim ask "Why did we choose SQLite?"   # LLM-synthesized answer from stored records (requires server)
lerim status --json                     # inspect projects, counts, queue, and recent activity
```

Use `lerim ask` when you need a synthesized answer across multiple records.
Use `lerim status` when you need visibility into projects, queue health, and stored record counts.

## How it works

Lerim runs in the background (via `lerim up` or `lerim serve`). It syncs your agent sessions, extracts decisions and learnings into the global context DB, and refines them over time through DB-backed extract, maintain, and ask flows.

Your job is to read and query existing context records when they are relevant. You do not write durable context directly — Lerim handles extraction automatically. Setup (`pip install lerim`, `lerim init`, `lerim project add .`, `lerim up`) is done by the user before you start.

## Tool contract

The DB-era tool surface is small on purpose.

- `trace_read`: read bounded trace chunks during extract
- `list_records`: browse exact recent or filtered records by time, kind, and status
- `search_records`: retrieve candidate records with local ONNX embeddings + `sqlite-vec` + FTS5 + RRF
- `fetch_records`: load selected records in concise or detailed form
- `create_record`: create a new durable record with explicit typed fields
- `update_record`: repair or clarify a durable record
- `archive_record`: archive a stale record
- `supersede_record`: mark a weaker record as replaced by a stronger one
- `context_query`: deterministic count/list queries for records, versions, and sessions
- `note`: keep extract-time findings in run state
- `prune`: reduce trace context pressure during long extract runs

Use the semantic tools above. Do not recreate file-era workflows like manual markdown scans, index maintenance, or raw storage edits.

## References

- Full CLI reference: [cli-reference.md](cli-reference.md)
