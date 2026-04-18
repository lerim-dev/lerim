# Lerim Test Suite

## Summary

The maintained test surface is DB-only.

What we test:

- unit tests for config, adapters, store, tools, CLI, API, daemon, and runtime
- targeted live verification when a change touches the real service path

What we do not keep anymore:

- file-based smoke tests
- file-based index checks
- file-based extraction / maintain / ask flows

## Quick reference

```bash
tests/run_tests.sh unit
uv run pytest tests/unit -q
```

For live verification after runtime changes:

```bash
uv run lerim up --build
uv run lerim status --json
uv run lerim sync --json
uv run lerim maintain --json
```

## Architecture under test

The current system is:

- canonical durable context in `~/.lerim/context.sqlite3`
- canonical session catalog in `~/.lerim/index/sessions.sqlite3`
- canonical run artifacts in `~/.lerim/workspace/`
- semantic agent tools: `trace_read`, `context_search`, `context_fetch`, `context_apply`, `note`, `prune`

## Fixtures

Shared fixtures live in `tests/conftest.py`.

Main ones:

- `tmp_lerim_root` — temporary global Lerim root
- `tmp_config` — config pointing at that root
- `TRACES_DIR` — normalized trace fixtures for supported adapters
