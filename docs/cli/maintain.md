# lerim maintain

Run one context-maintenance pass.

## Examples

```bash
lerim maintain
lerim maintain --dry-run
```

## What it does

`maintain` reads existing records and improves the graph:

- merge duplicates
- archive low-value records
- link related records
- supersede outdated records

It works on the database.

## Flow

```mermaid
flowchart TD
    A["Trigger: lerim maintain or daemon"] --> B["Maintain agent receives project context task"]

    B --> C["Prompt goal: keep memory useful, current, compact, and non-duplicative"]
    C --> D["Agent lists or searches active records"]
    D --> E["Agent fetches full records before any mutation"]

    E --> F{"What problem is found?"}
    F -- "duplicate or outdated truth" --> G["Use supersede_context to point old memory to newer truth"]
    F -- "verbose, weak, or report-like" --> H["Use revise_context to rewrite into reusable present-tense memory"]
    F -- "junk, obsolete, or low-value episode" --> I["Use archive_context"]
    F -- "still useful" --> J["Leave unchanged"]

    G --> K["SQLite context DB + record_versions"]
    H --> K
    I --> K
    J --> L{"More records to inspect?"}
    K --> L

    L -- "yes" --> D
    L -- "no" --> M["Maintain summary and artifacts"]
    M --> N{"Any records changed?"}
    N -- "yes" --> O["Refresh Working Memory for project"]
    N -- "no" --> P["Finish"]
```
