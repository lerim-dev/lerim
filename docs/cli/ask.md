# lerim ask

Query existing project context.

## Examples

```bash
lerim ask "What decisions do we have about auth?"
lerim ask "How is caching handled?" --scope project --project lerim-cli
```

## How it works

`ask` uses hybrid retrieval against the global context database and then fetches the full records needed for the answer.

```mermaid
flowchart TD
    A["User runs lerim ask"] --> B["Ask agent receives question and project scope"]

    B --> C["Prompt goal: answer only from retrieved Lerim records"]
    C --> D{"What kind of question is this?"}

    D -- "count, latest, date, current state" --> E["Use exact tools: count_context or list_context"]
    D -- "topic, rationale, explanation" --> F["Use search_context for hybrid semantic + lexical retrieval"]
    D -- "mixed question" --> G["Use exact filtering first, then search or inspect within that set"]

    E --> H{"Is the returned evidence enough?"}
    F --> H
    G --> H

    H -- "needs full source" --> I["Use get_context to fetch full records and versions"]
    H -- "enough" --> J["Synthesize answer"]

    I --> K{"Do records support the answer?"}
    K -- "yes" --> J
    K -- "no" --> L["Say the context does not contain enough evidence"]

    J --> M["Return answer, scope, projects used, optional debug trace"]
    L --> M
```

Use `--scope project` when you want one project only.
