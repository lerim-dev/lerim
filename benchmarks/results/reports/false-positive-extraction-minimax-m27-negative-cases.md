# Lerim False-Positive Extraction Diagnostic

- Generated: `2026-05-20T04:12:26.145634+00:00`
- Command: `benchmarks/lerim_evidence/false_positive_extraction.py --source-report '<private-source-report>' --output-dir benchmarks/results/raw/false-positive-extraction-minimax-m27-negative-cases`
- Source artifact: `private first-party extraction eval artifact`
- Source visibility: `private`
- Source digest: `b933d8037ca3068f3c771ed05366f255f42fd6a94e03069d94d3e77b1bd18ffc`
- Agent model: `minimax / MiniMax-M2.7`
- Judge model: `MiniMax-M2.7`
- Source cases: `47`
- Negative cases: `14`
- Aggregate-only public artifact: `True`
- Publication status: `diagnostic_development_guardrail_not_market_comparison`

## Headline

| Metric | Result |
|---|---:|
| Negative cases | 14 |
| No-durable cases | 5 |
| False-positive cases | 9 |
| Negative precision | 35.71% |
| False-positive case rate | 64.29% |
| Durable records on negative cases | 52 |
| Forbidden-concept score average | 82.80% |
| Signal-filtering score average | 21.43% |

## Dataset Slice

- Selection rule: `case.category == 'negative'`

## Public Artifact Boundary

- This diagnostic is derived from the negative/noise cases in the 47-case LLM-backed extraction artifact.
- It measures whether Lerim avoids durable records when labeled source sessions have no durable signal.
- Raw traces, case identifiers, extracted record text, tool payloads, forbidden concept text, per-case metrics, and judge details are intentionally excluded.
- Treat this as internal development evidence until rerun from a clean release state.
- Competitors have not been run on this private labeled eval, so their scores are not available.

Do not compare this diagnostic to LongMemEval retrieval-only metrics or market rows.
