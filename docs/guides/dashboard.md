# Dashboard

Lerim ships an open-source local dashboard in `dashboard/`.

The dashboard talks directly to the local JSON API exposed by `lerim serve`.
It is a read-only product surface for source sessions, runtime activity,
records, and graph exploration.

## Run Locally

```bash
lerim up
lerim dashboard
```

Open `http://localhost:3000`.

Use `lerim up --build` instead of `lerim up` when you want the backend built
from the local Dockerfile. `lerim dashboard` starts the local Next.js dev server
and prints the dashboard URL. It also installs dashboard npm dependencies when
they are missing.

The UI proxies `/api` to `http://localhost:8765` in development.

Use the CLI for write actions:

```bash
lerim ingest
lerim curate
lerim answer "What changed?"
lerim queue
```

## Related

- [CLI: lerim serve](../cli/serve.md) — local API + daemon loop
- [CLI: lerim dashboard](../cli/dashboard.md) — local dashboard launcher
- [CLI: lerim status](../cli/status.md) — runtime overview
