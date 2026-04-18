# config.toml Reference

This page documents the current DB-only config shape.

## Minimal example

```toml
[data]
dir = "~/.lerim"
# optional:
# context_db_path = "~/.lerim/context.sqlite3"

[server]
host = "127.0.0.1"
port = 8765
sync_interval_minutes = 30
maintain_interval_minutes = 60
sync_window_days = 7
sync_max_sessions = 50

[roles.agent]
provider = "minimax"
model = "MiniMax-M2.7"
api_base = ""
fallback_models = []
temperature = 1.0
top_p = 0.95
top_k = 40
max_tokens = 32000
parallel_tool_calls = true
max_iters_maintain = 50
max_iters_ask = 20
```

## Notes

- `dir` is the global Lerim root
- `context_db_path` is optional; default is `dir/context.sqlite3`
- there is one active model role today: `[roles.agent]`
- API keys come from environment variables, not TOML
