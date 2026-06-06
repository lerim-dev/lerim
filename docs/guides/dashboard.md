# Dashboard

Lerim ships an open-source local dashboard in `dashboard/`.

The dashboard talks directly to the local JSON API exposed by `lerim serve`.
It is mostly a local review surface for source sessions, runtime activity,
records, graph exploration, and skill update proposals. The Skills tab includes
write actions for applying or rejecting reviewed proposals.

## Run Locally

```bash
lerim up
lerim dashboard
```

Open `http://localhost:3000`.

Use `lerim up --build` instead of `lerim up` when you want the backend built
from the local Dockerfile. `lerim dashboard` starts the local Next.js dev server
and prints the dashboard URL. It also installs dashboard npm dependencies when
they are missing. If the backend is down after a local build, `lerim dashboard`
reuses the existing local image; it does not trigger a hidden Docker rebuild.

The UI proxies `/api` to `http://localhost:8765` in development.

Use the CLI for ingest, curate, answer, and queue actions:

```bash
lerim ingest
lerim curate
lerim answer "What changed?"
lerim queue
```

## Skills

The Skills tab reviews registered skill and instruction targets.

Use it after registering a target and running a refresh:

```bash
lerim skill target add ~/.agents/skills/clean-code \
  --description "Keep simplification guidance current"
lerim skill refresh clean-code
lerim dashboard
```

The page shows registered targets, update mode, auto-apply policy, proposal
status, guard status, validation status, unified diffs with line numbers, and
full-file previews with line numbers.

Apply writes the original target file only after validation, guard checks, and
stale-baseline checks pass. Reject leaves the target file unchanged and marks
the proposal terminal.

## Related

- [CLI: lerim serve](../cli/serve.md) — local API + daemon loop
- [CLI: lerim dashboard](../cli/dashboard.md) — local dashboard launcher
- [Skill Updates](skill-updates.md) — dashboard review flow for skill proposals
- [CLI: lerim skill](../cli/skill.md) — register targets and manage proposals
- [CLI: lerim status](../cli/status.md) — runtime overview
