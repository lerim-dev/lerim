# Lerim Dashboard

Local Next.js dashboard for the open-source Lerim runtime.

## Run Locally

Start the backend, then launch the UI from the `lerim` repo:

```bash
lerim up
lerim dashboard
```

Use `lerim up --build` instead of `lerim up` when you want the backend built
from the local Dockerfile.

`lerim dashboard` prints the dashboard link, starts the local Next.js dev server,
and installs dashboard npm dependencies if they are missing. The UI proxies
`/api` to the backend at `http://localhost:8765`.

For manual dashboard development against a backend on another port, set
`LERIM_API_URL`, for example:

```bash
LERIM_API_URL=http://127.0.0.1:18765 npm run dev -- --port 3002
```

The dashboard is read-only. Use the CLI for write actions such as `lerim ingest`,
`lerim curate`, `lerim answer`, and queue retry/skip.
