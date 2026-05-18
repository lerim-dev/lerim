# Incident Ops Demo

Incident examples live in the monorepo eval template, not in `lerim-cli`:

```text
lerim-cloud/evals/data/traces/
lerim-cloud/evals/data/labels/
lerim-cloud/evals/verticals/incident_ops/
```

Import an incident trace:

```bash
lerim trace import ../lerim-cloud/evals/data/traces/incident_webhook_outage_002.jsonl \
  --source-name incident-agent \
  --source-profile ops \
  --scope-type domain \
  --scope incident-ops
```

Inspect the resulting cards:

```bash
lerim context cards --profile ops
lerim context cards --profile ops --type root_cause
lerim context cards --profile ops --type runbook_gap
```

Incident cards should distinguish confirmed root causes from rejected
hypotheses, mitigations from failed mitigations, and source-of-truth references
from stale local notes.

Do not put incident datasets, expected files, or converter outputs under
`lerim-cli`. Stage conversion work under `lerim-cloud/evals/verticals/incident_ops`
and promote release-ready traces/labels into `lerim-cloud/evals/data`.
