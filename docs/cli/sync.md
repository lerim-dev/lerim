# lerim sync

Discover new sessions and extract context records.

## Examples

```bash
lerim sync
lerim sync --window 30d
lerim sync --run-id <run_id> --force
lerim sync --agent claude,codex
```

## What it does

- scans connected agent traces
- matches sessions to registered projects
- queues work
- runs extraction
- writes records into `~/.lerim/context.sqlite3`

## Flow

```mermaid
flowchart TD
    A["Trigger: lerim sync or daemon"] --> B["Discover and queue changed sessions"]
    B --> C["Extract agent receives one session trace"]

    C --> D["Prompt goal: turn this session into durable project memory"]
    D --> E["Agent reads trace chunks with read_trace"]
    E --> F{"Has the agent read enough of the trace?"}
    F -- "no" --> E
    F -- "yes" --> G["Agent identifies candidate memories: episode, decisions, preferences, constraints, facts, references"]

    G --> H{"Could this update or duplicate existing memory?"}
    H -- "yes" --> I["Use search_context/get_context to inspect existing records"]
    H -- "no" --> J["Prepare new records"]

    I --> K{"Existing record should change?"}
    K -- "revise" --> L["Use revise_context on fetched record"]
    K -- "new memory" --> J
    K -- "no durable value" --> M["Do not write"]

    J --> N["Use save_context for supported durable records"]
    L --> O["SQLite context DB + record_versions"]
    N --> O
    M --> P["Completion summary"]
    O --> P
    P --> Q["Sync artifacts: manifest, agent log, trace"]
```

## Notes

- `--no-extract` only indexes and queues work
- `--dry-run` previews the operation
