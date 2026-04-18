# Lerim Python Package

## Summary

This folder contains the Lerim runtime package.
Current architecture is PydanticAI-only for agent execution.
Durable Lerim context now lives in the global SQLite store at `~/.lerim/context.sqlite3`.
Project identity is used to separate records by repo inside that shared DB.

The package is organized by feature boundary:

- `agents/`: agent flows (`extract.py`, `maintain.py`, `ask.py`), semantic context tools (`tools.py`), typed contracts (`contracts.py`)
- `server/`: CLI (`cli.py`), HTTP API (`httpd.py`), daemon (`daemon.py`), runtime orchestrator (`runtime.py`), Docker/runtime API helpers (`api.py`)
- `config/`: config loading (`settings.py`), PydanticAI model builders (`providers.py`), tracing and logging setup
- `context/`: global SQLite context store, project identity, and retrieval/write helpers
- `transcripts/`: transcript normalization helpers used while reading raw session traces (`transcript.py`)
- `sessions/`: session catalog and queue state (`catalog.py`)
- `adapters/`: session readers for Claude, Codex, Cursor, OpenCode
- `cloud/`: hosted auth/shipper integration (`auth.py`, `shipper.py`)
- `skills/`: bundled skill markdown files

## How to use

If you are new to the codebase, read in this order:

1. `server/cli.py` for the public command surface.
2. `server/daemon.py` for sync/maintain scheduling and lock flow.
3. `server/runtime.py` for runtime orchestration across extract/maintain/ask.
4. `context/store.py` for the canonical SQLite schema and retrieval/write logic.
5. `agents/tools.py` for the semantic agent tool surface (`trace_read`, `context_search`, `context_fetch`, `context_apply`, `note`, `prune`).
6. `agents/extract.py`, `agents/maintain.py`, `agents/ask.py` for PydanticAI agent behavior.
7. `transcripts/transcript.py` only when you need to inspect how raw agent traces are normalized before extraction; it is not part of the durable context store.
