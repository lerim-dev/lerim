# lerim trace

Import one explicit trace file with a source profile.

## Overview

`lerim trace import` is a host-only one-file import utility. MCP-submitted
traces also have local recovery commands under `lerim trace submissions` and
`lerim trace retry`.

Built-in `connect` adapters discover sessions from supported local tools such as
Claude Code, Codex CLI, Cursor, OpenCode, and pi.

Custom agents should normally use custom trace folders:

```bash
lerim project add ~/lerim-traces/support-clean --type custom
lerim ingest --agent custom
```

Use `trace import` when you intentionally want to import one standalone file
into a selected scope and profile, such as `support` or `ops`.
If the bundled profiles do not fit your workflow, create one with
[Customize Lerim For Your Use Case](../guides/custom-source-profiles.md).

## Syntax

```bash
lerim trace import <path> \
  --source-name <name> \
  --source-profile <profile> \
  --scope-type <project|domain|user|session|workspace|custom> \
  --scope <scope> \
  [--session-id <id>] \
  [--force]
```

```bash
lerim trace submissions --status failed
lerim trace retry <submitted_trace_path>
```

## Example

```bash
lerim trace import ./support-agent-run.jsonl \
  --source-name support-bot \
  --source-profile support \
  --scope-type domain \
  --scope support
```

The docs include small example traces for learning the command shape. Use your
own cleaned source sessions for actual evaluation or production import:

```bash
lerim trace import docs/examples/traces/incident-agent-run.jsonl \
  --source-name incident-agent \
  --source-profile ops \
  --scope-type domain \
  --scope incident-ops
```

## What Happens

1. Lerim reads a JSON, JSONL, or text trace file.
2. It normalizes the trace into Lerim's compact user/assistant event shape.
3. It writes the normalized copy under the Lerim workspace imports directory.
4. It registers the selected scope in the context store.
5. If the same session id already points at identical normalized content, it
   skips duplicate extraction unless `--force` is set.
6. It runs trace ingestion and writes any durable records into the shared context store.

## Submitted Trace Recovery

When an MCP client calls `lerim_trace_submit`, Lerim first stores the submitted
payload under the workspace `mcp-submissions` directory and writes a sidecar
manifest ending in `.lerim-submission.json`.

If extraction fails because the model provider, network, or runtime is
temporarily unavailable, the MCP response includes:

- `submitted_trace_path`
- `submission_manifest_path`
- `retry_command`
- `attempt_count`

List recent submissions:

```bash
lerim trace submissions
lerim trace submissions --status failed
```

Retry a failed submission with the saved source, profile, scope, and session
metadata:

```bash
lerim trace retry ~/.lerim/workspace/mcp-submissions/2026/05/19/example.json
```

Use `--force` only when you intentionally want to re-extract an already
imported identical submission.

## Trace Shape

For JSONL, each line can be a message-like object:

```json
{"role":"customer","content":"The renewal customer asked for legal approval.","timestamp":"2026-05-16T09:00:00Z"}
{"role":"agent","content":"Checked policy notes and opened a follow-up task.","timestamp":"2026-05-16T09:02:00Z"}
```

For JSON, Lerim accepts either an array of message-like objects or an object with
a `messages`, `events`, `trace`, `steps`, or `items` list.

If a JSON wrapper includes `session_id`, `sessionId`, `id`, `run_id`, or
`runId`, Lerim uses that as the default session id unless `--session-id`
overrides it. Otherwise, the normalized trace content hash provides a stable
session id, so identical payloads do not get re-extracted just because the file
path changed.

Plain text is accepted as one trace message. It is useful for quick pilots, but
structured JSON or JSONL is better because timestamps, actor roles, source
artifacts, decisions, evidence links, and workflow identifiers survive import.

## Custom Cleaning

Teams may run their own exporter, cleaner, or redaction script before import.
That is the right place to remove secrets, regulated fields, oversized tool
payloads, screenshots, binary blobs, and source-specific noise.

Lerim's ingestion flow is selective about durable signal: routine traces can
produce no permanent durable record, and useful records are compacted into
evidence-backed context records. That filtering is not a replacement for
customer-owned privacy, retention, or compliance cleaning before a trace enters
Lerim.

## Scope

Scope decides where imported context belongs.

| Scope type | Good fit |
|------------|----------|
| `project` | Repository or implementation workflow |
| `domain` | Support, research, security, revenue, or operations workflow |
| `workspace` | A company workspace or business unit |
| `session` | One isolated run |
| `user` | Personal assistant context |
| `custom` | Customer-defined boundary |

For ongoing custom-agent workflows, prefer
[Custom Trace Folders](../guides/custom-trace-folders.md).
