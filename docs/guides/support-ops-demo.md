# Support Ops Demo

This demo uses a tiny checked-in example trace to show the import shape. Replace
it with your own cleaned support-agent source session for real evaluation.

Import a support trace:

```bash
lerim trace import docs/examples/traces/support-agent-run.jsonl \
  --source-name support-agent \
  --source-profile support \
  --scope-type domain \
  --scope support-ops
```

Inspect the resulting records:

```bash
lerim context records --profile support
lerim context records --profile support --type constraint
lerim context records --profile support --type fact
```

Support records should preserve strict reusable context: customer constraints,
policy-backed facts, source-of-truth evidence, known fixes, failed paths, and
handoff boundaries when they are supported by the trace.

Do not put private customer datasets or converter outputs under public docs.
Use customer-owned storage for raw traces and commit only small sanitized
examples when a public example is useful.
