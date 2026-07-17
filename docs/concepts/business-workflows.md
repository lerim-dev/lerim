# Business Workflows

Lerim is useful when a team runs repeated AI workflows and keeps losing the
operating context, correction signal, and evaluation evidence between runs.

The pattern is:

1. an agent completes work inside a business process
2. the trace contains evidence, decisions, constraints, open questions, and handoffs
3. Lerim extracts the reusable signal
4. Lerim writes compact context records and eval-ready assets with source evidence
5. the next agent starts with compact, cited context instead of a raw transcript
6. approved corrections stay as cited context for future runs.

Support, incident/security operations, research, compliance, revenue, and other workflows can use custom clean traces today when the source owner handles export, redaction, and retention. Research, revenue, security, and other workflows can use custom clean traces today when the source owner handles export, redaction, and retention. Support, incident, research, and compliance already have bundled signal packs; revenue, security, and other verticals use the generic profile or a custom YAML profile.

## Support operations

Support teams preserve customer constraints, known fixes, failed fixes,
escalation reasons, policy-backed facts, source-of-truth evidence, and handoffs.

Example import:

```bash
lerim trace import docs/examples/traces/support-agent-run.jsonl \
  --source-name support-agent \
  --source-profile support \
  --scope-type domain \
  --scope support-ops
```

Example question:

```bash
lerim answer "What do we already know about this customer escalation pattern?"
```

## Operations and incidents

Operations teams preserve confirmed root causes, rejected hypotheses,
mitigations, failed mitigations, runbook gaps, owner decisions, source-of-truth
facts, and follow-up risks.

Example question:

```bash
lerim answer "What risks were still open after the last carrier-delay incident?"
```

## Engineering automation

Engineering teams can retain architecture decisions, failed tests, repo
conventions, release lessons, and operational constraints. This is one of several
workflows where the same context compiler applies.

Example question:

```bash
lerim answer "What release constraints did previous agents discover?"
```

## Current source boundary

The open-source package includes the trace-to-context foundation, supported
source adapters, and custom clean-trace folders. Customer pilots can start by
choosing one workflow, cleaning its traces into Lerim canonical JSONL, and
registering that folder as a custom project or importing explicit traces with
`lerim trace import`.

For custom agents today, the practical path is:

```bash
lerim project add ~/lerim-traces/support-clean --type custom
lerim ingest --agent custom
lerim context records --profile support
```

If the source trace contains customer-specific noise or sensitive fields, run a
customer-owned cleaner before the files enter that folder. Lerim filters for
durable business signal, but pre-ingest cleaning is still the right boundary for
secrets, regulated data, large raw tool outputs, and retention policy.
