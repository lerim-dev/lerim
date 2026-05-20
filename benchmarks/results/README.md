# Benchmark Results

This directory is generated evidence, not the main public documentation.

| Path | Meaning |
| --- | --- |
| `raw/` | Source-of-truth benchmark artifacts. Use `report.json` for numbers. |
| `reports/` | Generated Markdown copies for review and audit. |
| `reports/index.md` | Generated index over current report artifacts. |

The public docs are split by audience:

- `../../docs/benchmarks/index.md`: benchmark hub and reporting rules
- `../../docs/benchmarks/lerim-results.md`: Lerim-only results and commands
- `../../docs/benchmarks/market-comparison.md`: market comparison with sources

Rules:

- Do not edit generated numbers by hand.
- Do not publish partial slices as final results.
- Ignored development artifacts may exist during private evaluation, but public
  docs and `reports/index.md` should only point to public, non-ignored
  artifacts.
- Keep exploratory planning material outside this generated results tree.
- Public competitor numbers must be source-backed and must state whether they
  came from a local rerun, pinned upstream artifact, or cited public report.
