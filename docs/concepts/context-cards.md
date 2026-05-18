# Context Cards

Context cards are the product-facing shape of durable records.

`record_kind` is storage-level:

- `episode`
- `fact`
- `decision`
- `preference`
- `constraint`
- `reference`

`card_type` is workflow-level:

- `known_fix`
- `failed_path`
- `handoff`
- `source_of_truth`
- `root_cause`
- `mitigation`
- `runbook_gap`
- `guardrail_candidate`

A fact may render as a known fix, failed path, source-of-truth card, or
root-cause card depending on source profile.

Example:

```text
record_kind = constraint
card_type = escalation
source_profile = support
```

List cards:

```bash
lerim context cards --profile support
lerim context cards --profile ops
lerim context cards --type failed_path
lerim context cards --profile support --lifecycle-status proposed
```

Local developer traces can write cards as active immediately. Support and ops
profiles default new durable cards to proposed so a review surface can approve
them before operational reuse.
