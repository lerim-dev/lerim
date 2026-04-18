# lerim status

Show runtime state.

## Examples

```bash
lerim status
lerim status --live
lerim status --scope project --project lerim-cli
lerim status --json
```

## What it shows

- connected agents
- context record counts
- indexed session counts
- sync discovery window used for queueing
- queue state
- per-project stream state
- recent sync and maintain activity

## Stream states

- `running`: a project has an active extraction job now
- `queued`: a project has pending work waiting to run
- `quiet`: past in-scope sessions were already processed; no queued work now
- `idle`: no indexed sessions exist for that project in the current sync window
- `blocked`: the oldest queued job is dead-lettered and needs retry or skip
