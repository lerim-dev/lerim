# Lerim Extraction Quality Benchmark

- Generated: `2026-05-20T04:12:26.133034+00:00`
- Command: `benchmarks/lerim_evidence/extraction_quality.py --source-report '<private-source-report>' --output-dir benchmarks/results/raw/extraction-minimax-m27-full-47`
- Source artifact: `private first-party extraction eval artifact`
- Source visibility: `private`
- Source digest: `b933d8037ca3068f3c771ed05366f255f42fd6a94e03069d94d3e77b1bd18ffc`
- Agent model: `minimax / MiniMax-M2.7`
- Judge model: `MiniMax-M2.7`
- Dataset cases: `47`
- Aggregate-only public artifact: `True`
- Publication status: `development_baseline_not_launch_grade`

## Headline

| Metric | Result |
|---|---:|
| Task completion | 96.97% |
| Quality average | 62.45% |
| Quality gate pass | 46.81% |
| Hard gate pass | 21.28% |
| Concept recall average | 61.16% |
| Required concept coverage | 59.57% |
| Kind alignment | 93.97% |
| Record precision average | 70.34% |
| Faithfulness average | 69.20% |
| Claim faithfulness | 40.43% |
| Negative precision | 35.71% |
| Signal filtering | 29.79% |
| Evidence coverage | 99.65% |
| Evidence validity | 100.00% |

## Dataset Coverage

- Cases: `47` / `47`
- Dataset coverage: `100.00%`
- Case failures: `0`


## Public Artifact Boundary

- This is an aggregate-only public report derived from a full LLM-backed extraction artifact.
- Raw traces, extracted record text, tool payloads, case identifiers, per-case metrics, and judge details are intentionally excluded.
- Treat this as development baseline evidence until rerun from a clean release state.
- These metrics measure trace-to-context extraction quality, not LongMemEval retrieval or answer-generation accuracy.
- Competitors have not been run on this private labeled eval, so their scores are not available.

Do not compare these extraction metrics to LongMemEval retrieval-only metrics.
Competitor scores are not available for this private labeled eval.
