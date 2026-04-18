# Lerim Test Suite

## Summary

The maintained test surface is DB-only.

What we test:

- unit tests for config, adapters, store, tools, CLI, API, daemon, and runtime
- smoke tests for quick real-LLM extract sanity
- integration tests for real extract, maintain, and semantic ask flows
- end-to-end tests for the full runtime cycle on the DB-only system

What we do not keep anymore:

- file-based smoke tests
- file-based index checks
- file-based extraction / maintain / ask flows

## Quick reference

```bash
tests/run_tests.sh unit
uv run pytest tests/unit -q
```

For live QA after runtime changes:

```bash
tests/run_tests.sh smoke
tests/run_tests.sh integration
tests/run_tests.sh e2e
```

## Architecture under test

The current system is:

- canonical durable context in `~/.lerim/context.sqlite3`
- canonical session catalog in `~/.lerim/index/sessions.sqlite3`
- canonical run artifacts in `~/.lerim/workspace/`
- local semantic retrieval via ONNX embeddings + `sqlite-vec` + FTS5 + RRF
- extract tools: `trace_read`, `search_records`, `fetch_records`, `create_record`, `update_record`, `note`, `prune`
- maintain tools: `search_records`, `fetch_records`, `update_record`, `archive_record`, `supersede_record`
- ask tools: `search_records`, `fetch_records`, `context_query`

## Fixtures

Shared fixtures live in `tests/conftest.py`.

Main ones:

- `tmp_lerim_root` — temporary global Lerim root
- `tmp_config` — config pointing at that root
- `live_lerim_root` — temporary isolated global root for real LLM suites
- `live_config` — current provider/model config copied into that isolated root
- `live_repo_root` — temporary project root for live runtime flows
- `live_runtime` — runtime bound to the isolated root and temp project
- `TRACES_DIR` — normalized trace fixtures for supported adapters

Live QA helpers live in `tests/live_helpers.py`.
They audit:

- schema exactness
- dead forbidden tables
- agent tool use from `agent_trace.json`
- DB quality after sync and maintain
