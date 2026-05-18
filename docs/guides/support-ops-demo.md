# Support Ops Demo

Support examples live in the monorepo eval template, not in `lerim-cli`:

```text
lerim-cloud/evals/data/traces/
lerim-cloud/evals/data/labels/
lerim-cloud/evals/verticals/support_ops/
```

Import a support trace:

```bash
lerim trace import ../lerim-cloud/evals/data/traces/support_refund_escalation_001.jsonl \
  --source-name support-agent \
  --source-profile support \
  --scope-type domain \
  --scope support-ops
```

Inspect the resulting cards:

```bash
lerim context cards --profile support
lerim context cards --profile support --type escalation
lerim context cards --profile support --type handoff
```

Support cards should preserve workflow language: customer constraints, known
fixes, failed fixes, escalation reasons, policy references, source-of-truth
links, handoffs, repeated-waste patterns, and guardrail candidates.

Do not put support datasets, expected files, or converter outputs under
`lerim-cli`. Stage conversion work under `lerim-cloud/evals/verticals/support_ops`
and promote release-ready traces/labels into `lerim-cloud/evals/data`.
