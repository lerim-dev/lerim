# Incident Ops Demo

This demo uses a tiny checked-in example trace to show the import shape. Replace
it with your own cleaned incident-agent source session for real evaluation.

Import an incident trace:

```bash
lerim trace import docs/examples/traces/incident-agent-run.jsonl \
  --source-name incident-agent \
  --source-profile ops \
  --scope-type domain \
  --scope incident-ops
```

Inspect the resulting records:

```bash
lerim context records --profile ops
lerim context records --profile ops --type fact
```

Incident records should preserve confirmed root causes, rejected hypotheses,
mitigations, failed paths, owner decisions, and source-of-truth facts only
when the trace supports them.

Do not put private incident datasets or converter outputs under public docs.
Use team-owned storage for raw traces and commit only small sanitized examples
when a public example is useful.
