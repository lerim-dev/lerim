# lerim dashboard

Shows that dashboard UI is not released yet and lists CLI alternatives.

## Overview

This command prints a temporary notice and lists CLI commands you can use in the meantime.

## Syntax

```bash
lerim dashboard
```

## Examples

```bash
lerim dashboard
```

Sample output:

```
  Lerim Dashboard is moving to the cloud.
  The new dashboard will be available at https://lerim.dev

  In the meantime, use these CLI commands:
    lerim status     - system overview
    lerim ask        - query your stored context
    lerim queue      - view session processing queue
    lerim sync       - process new sessions
    lerim maintain   - refine stored records
```

## See also

- [lerim status](status.md) — runtime state overview
- [lerim serve](serve.md) — HTTP API + daemon loop
- [Dashboard (Coming Soon)](../guides/dashboard.md)
