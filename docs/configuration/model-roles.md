# Model Roles

Lerim uses one active model role today.

## `[roles.agent]`

This role powers:

- `sync` extraction orchestration
- `maintain`
- `ask`

Important fields:

- `provider`
- `model`
- `api_base`
- `fallback_models`
- `temperature`
- `top_p`
- `top_k`
- `max_tokens`
- `parallel_tool_calls`
- `max_iters_maintain`
- `max_iters_ask`
