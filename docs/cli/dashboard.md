# lerim dashboard

Starts the local dashboard UI.

## Overview

`lerim dashboard` starts the local Next.js dashboard dev server, prints the
dashboard URL, and points it at the running Lerim API. If the backend API is not
reachable, the command starts it with the same Docker runtime path as `lerim up`.

For local backend rebuilds, run `lerim up --build` first, then `lerim dashboard`.

## Syntax

```bash
lerim dashboard [--port PORT]
```

## Examples

```bash
lerim up
lerim dashboard
```

Build the backend locally before opening the dashboard:

```bash
lerim up --build
lerim dashboard
```

Run the UI on a different port:

```bash
lerim dashboard --port 3001
```

## Options

<div class="param-block">
  <p><code>--port PORT</code></p>
  <p class="param-desc">Dashboard UI port. Defaults to <code>3000</code>.</p>
</div>

## See also

- [lerim status](status.md) — runtime state overview
- [lerim serve](serve.md) — HTTP API + daemon loop
- [Dashboard Guide](../guides/dashboard.md)
