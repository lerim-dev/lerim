# CLI Overview

The CLI has two groups of commands.

## Host-only commands

These work on local files, Docker, or config:

- `lerim init`
- `lerim project`
- `lerim connect`
- `lerim up`
- `lerim down`
- `lerim logs`

## Server-backed commands

These talk to the running Lerim service:

- `lerim sync`
- `lerim maintain`
- `lerim ask`
- `lerim status`

## Durable context

The CLI works with the global context database.
Project commands register scope only.
