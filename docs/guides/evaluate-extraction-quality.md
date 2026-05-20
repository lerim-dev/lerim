# Evaluate Extraction Quality

Do not evaluate Lerim by the number of memories created.

Evaluate whether the compiler produced a small set of useful, supported,
non-duplicate context records:

- precision
- usefulness
- evidence coverage
- duplicate rate
- scope compatibility
- expected record kind alignment
- future reuse

Keep extraction eval data separate from the public package unless the traces are
small, sanitized examples. A publishable eval needs:

- source-session trace files
- labels for expected durable records and no-signal cases
- a runner that feeds traces into Lerim
- a judge or deterministic scorer with saved raw outputs
- sanitized public reports that exclude raw private trace text

The public benchmark reports in this repo are generated artifacts. The private
source traces and judge details are intentionally not shipped with the package.
