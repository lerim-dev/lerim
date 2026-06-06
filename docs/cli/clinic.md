# lerim clinic

`lerim clinic` reads or refreshes a project-level Run Clinic diagnostic for the
resolved project.

It is not agent startup memory. Use `lerim context-brief show` for durable
startup context and `lerim working-memory show` for short-term continuation
context. Clinic is for humans reviewing recurring project patterns, verification
gaps, risks, and improvement opportunities.

## Commands

```bash
lerim clinic show
lerim clinic status
lerim clinic path
lerim clinic refresh
lerim clinic refresh --force
```

| Subcommand | Description |
|------------|-------------|
| `show` | Print live freshness plus the current `RUN_CLINIC.md` |
| `status` | Print availability, generated time, trend window, changed-record count, report path, latest run folder, and suggested action |
| `path` | Print the stable expected current artifact path |
| `refresh` | Generate dated Markdown and JSON report artifacts, then update the stable current copies |

| Flag | Description |
|------|-------------|
| `--project` | Registered project name or path. Defaults to the project resolved from cwd |
| `--force` | On `refresh`, regenerate even when the current Clinic is fresh |
| `--json` | Emit structured JSON for `status`, `path`, and `refresh` |

## Output Location

Current artifacts:

```text
~/.lerim/workspace/current/<project_id>/RUN_CLINIC.md
~/.lerim/workspace/current/<project_id>/RUN_CLINIC.report.json
~/.lerim/workspace/current/<project_id>/RUN_CLINIC.manifest.json
```

Dated run artifacts:

```text
~/.lerim/workspace/YYYY/MM/DD/run-clinic/run-clinic-<timestamp>-<id>/
```

## Refresh Behavior

`show` never refreshes. It reads the current artifact and computes a live
freshness preface from SQLite.

`refresh` skips when the current artifact exists, no project records changed
after its `generated_at`, and the artifact is less than 24 hours old. It
regenerates when records changed, when `--force` is passed, or when the trend
diagnosis is old.
