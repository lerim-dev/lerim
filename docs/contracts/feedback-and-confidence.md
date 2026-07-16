# Feedback and Confidence Contract

This is the durable contract for the per-record feedback signal and the earned
per-record confidence score. Retrieval and dashboard lanes should read from
this document instead of re-deriving these shapes from `store.py`.

## Summary

Every context record now carries an earned `confidence` score in `[0.0, 1.0]`.
Confidence starts at `0.5` for every record and moves only when a caller
records an explicit feedback signal through `ContextStore.record_feedback`.
Feedback is intentionally a separate axis from record content:

- recording feedback never edits `title`/`body`/`status`/etc.
- recording feedback never creates a `record_versions` row.
- recording feedback never bumps the records index generation (it does not
  touch FTS or embeddings).
- editing record content (`update_record`, `archive_record`, `supersede_record`)
  never changes `confidence`.

## Data model

### `records.confidence`

```
confidence REAL NOT NULL DEFAULT 0.5
```

Added via migration (`ContextStore._ensure_record_confidence_schema`) to the
`records` table only. `record_versions` does **not** have a `confidence`
column — confidence is not versioned, so version rows always report the
default `0.5` when read back through `_record_row_to_dict`.

### `record_feedback` table

```
CREATE TABLE record_feedback (
    feedback_id TEXT PRIMARY KEY,
    record_id TEXT NOT NULL,
    signal TEXT NOT NULL,
    note TEXT,
    source_session_id TEXT,
    created_at TEXT NOT NULL
);
```

One row per feedback event. Indexed on `record_id`. There is no foreign key
from `record_feedback.record_id` to `records.record_id` — this keeps
`reset_project_memory`/`count_project_memory` (which delete/count `records`
without first deleting `record_feedback`) from raising foreign-key errors.

## Record JSON shape

Every record dict returned by the store (`fetch_record`, `query`, search hits
via `_record_row_to_dict`) now includes:

```json
{
  "record_id": "rec_...",
  "...": "... existing fields unchanged ...",
  "confidence": 0.5
}
```

- Type: `float`, range `[0.0, 1.0]`. A record whose confidence has been driven
  all the way down to `0.0` (or up to `1.0`) by feedback reads back as that
  real value everywhere — `_record_row_to_dict` distinguishes "column absent"
  (pre-migration row) from "value is a genuine `0.0`" by checking `is None`,
  not by falling back on `... or DEFAULT_RECORD_CONFIDENCE` (that pattern
  would treat an earned `0.0` as missing and silently report `0.5` instead;
  `record_feedback`'s own current-confidence read applies the same `is None`
  guard, so a *subsequent* feedback call after reaching `0.0` recomputes its
  delta from the true floor, not a phantom `0.5`).
- Default: `0.5` for every record that has never received feedback, and for
  any row read before the column existed (`_row_value` returns `None` when
  the column is absent, which maps to `DEFAULT_RECORD_CONFIDENCE`).
- This field flows through every reader unchanged: CLI `lerim query records
  list`/`lerim context records`, the HTTP `/api/query` and `/api/records/{id}`
  routes, the `lerim_records_list`/`lerim_context_search` MCP tools, and the
  cloud shipper's context-record export.

## Feedback signal enum

Canonical values (`lerim.context.spec.FeedbackSignal` /
`ALLOWED_FEEDBACK_SIGNALS`):

| Signal    | Meaning                                   | Confidence delta |
|-----------|--------------------------------------------|------------------|
| `used`    | The record was retrieved and used as-is    | `+0.05`          |
| `correct` | The record's content was verified correct  | `+0.15`          |
| `confirm` | An independent pass re-confirmed the record | `+0.15`         |
| `wrong`   | The record's content was verified wrong    | `-0.25`          |

Any other value raises `ValueError("invalid_feedback_signal:<value>")`.

### Confidence update rule

Deterministic and bounded — no LLM involved:

```
next_confidence = clamp(current_confidence + delta[signal], 0.0, 1.0)
```

Implemented in `lerim.context.spec.next_record_confidence(current, signal)`.

## Store API

### `ContextStore.record_feedback(record_id, signal, *, note=None, source_session_id=None) -> dict`

1. Raises `ValueError("invalid_feedback_signal:<value>")` if `signal` is not
   one of the four allowed values.
2. Opens one `BEGIN IMMEDIATE` transaction and, on that same connection, reads
   `records.confidence` for `record_id`; raises
   `ValueError("record_not_found:<record_id>")` if no row matches. The read
   happens inside this locked transaction (not via a separate `fetch_record()`
   call beforehand) so two concurrent `record_feedback` calls for the same
   `record_id` cannot both read the same stale confidence and have the second
   writer silently clobber the first.
3. In that same transaction: inserts a `record_feedback` row, then runs
   `UPDATE records SET confidence = ? WHERE record_id = ?` with the recomputed
   value. Does not call `_insert_record_version` or
   `_bump_records_index_generation`.
4. Returns:

```json
{"record_id": "rec_...", "confidence": 0.65, "signal": "correct"}
```

### `ContextStore.list_feedback(record_id) -> list[dict]`

Returns every feedback row for one record, oldest first, exportable for
offline/private evals:

```json
[
  {
    "feedback_id": "fb_...",
    "record_id": "rec_...",
    "signal": "correct",
    "note": "Confirmed in prod incident review",
    "source_session_id": "sess_...",
    "created_at": "2026-07-16T00:00:00+00:00"
  }
]
```

## Server API (`lerim.server.api`)

### `api_feedback(record_id, signal, *, note=None, source_session_id=None, scope="all", project=None) -> dict`

Scope resolution mirrors `api_query`: `project`/`scope` are resolved through
`_resolve_selected_projects` purely to validate the `project` token and to
populate `projects_used`/`scope` in the response — `record_id` is a global
identifier, so the underlying store call is not project-filtered.

> **Known gap, pending a product decision:** this means any caller can submit
> feedback against any `record_id` in the entire global `context.sqlite3`, in
> any project, regardless of the `scope`/`project` value supplied. In
> practice this is currently unreachable through real entry points — the CLI
> `feedback` subcommand, the `lerim_context_feedback` MCP tool, and the HTTP
> `POST /api/records/{id}/feedback` body handler have no `project`/`scope`
> parameter, so every real caller uses the defaults (`scope="all"`,
> `project=None`). Two ways to close this, neither applied yet: (a) accept
> global-scope feedback as intentional (record ids are unguessable UUIDs) and
> drop this unused scope/project machinery from `api_feedback`, or (b) thread
> `project_ids` through `record_feedback`/`fetch_record` to actually enforce
> scope *and* expose `--project`/`scope` consistently at the CLI/MCP/HTTP
> layers so the enforcement is reachable and callers have a way to satisfy
> it. Do not implement half of (b) (store/api enforcement without CLI/MCP/HTTP
> exposure): with today's default `scope="all"`, that would silently resolve
> to "all currently-registered projects in the local config" and reject
> feedback for any record whose project is not currently registered locally,
> with no override available to callers.

Success:

```json
{
  "record_id": "rec_...",
  "confidence": 0.65,
  "signal": "correct",
  "error": false,
  "projects_used": [],
  "scope": "all"
}
```

Failure shapes (same convention as `api_query`):

```json
{"error": true, "message": "Project not found: bogus", "projects_used": []}
{"error": true, "message": "invalid_feedback_signal:bogus", "projects_used": [], "status_code": 400}
{"error": true, "message": "record_not_found:rec_missing", "projects_used": [], "status_code": 400}
{"error": true, "message": "Context query storage is unavailable.", "projects_used": [], "status_code": 503}
```

### `api_feedback_list(record_id) -> dict`

```json
{"record_id": "rec_...", "rows": [...], "count": 1, "error": false}
```

or `{"error": true, "message": "Context query storage is unavailable.", "status_code": 503}`.

## HTTP endpoint

### `POST /api/records/{record_id}/feedback`

Request body:

```json
{
  "signal": "correct",
  "note": "optional free text",
  "source_session_id": "optional session id"
}
```

`signal` is required (400 `Missing 'signal'` if blank). Response body is the
`api_feedback(...)` payload (200 on success). Errors from `api_feedback` map
`status_code` (400/503) onto the HTTP response status.

### `GET /api/records/{record_id}/feedback`

Response body is the `api_feedback_list(record_id)` payload (200 on success,
503 if the context store is unavailable).

## CLI

```
lerim feedback <record_id> <used|correct|wrong|confirm> [--note TEXT] [--json]
```

- `record_id` and `signal` are positional; `signal` is argparse-validated
  against `ALLOWED_FEEDBACK_SIGNALS`.
- `--json` prints the `api_feedback(...)` payload as JSON and exits `1` when
  `error` is `true`.
- Without `--json`, a failure prints `message` to stderr and exits `1`;
  success prints the JSON payload to stdout and exits `0`.

## MCP tool

### `lerim_context_feedback(record_id, signal, note=None, source_session_id=None) -> dict`

Registered immediately after `lerim_records_list`. This is **not** a
memory-save tool — `record_id` must reference a record that already exists;
it never creates new durable context. Blank `record_id`/`signal` are rejected
locally (`{"error": true, "message": "record_id_required"}` /
`{"error": true, "message": "signal_required"}`) before reaching the store;
all other validation/error shapes match `api_feedback(...)` above.
