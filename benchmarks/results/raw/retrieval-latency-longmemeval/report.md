# Lerim Retrieval Latency Benchmark

- Generated: `2026-05-19T07:32:59.889546+00:00`
- Command: `benchmarks/lerim_evidence/retrieval_latency.py --local-files-only --sizes 100,1000 --query-count 25 --iterations 3 --output-dir benchmarks/results/raw/retrieval-latency-longmemeval`
- Dataset snapshot: `98d7416c24c778c2fee6e6f3006e7a073259d48f`
- Queries: `25`
- Iterations: `3`

| Corpus records | Ops | p50 | p90 | p99 | Avg hits |
|---:|---:|---:|---:|---:|---:|
| 100 | 75 | 8.65 ms | 9.15 ms | 9.70 ms | 20.0 |
| 1000 | 75 | 32.40 ms | 34.17 ms | 54.47 ms | 20.0 |

## Methodology Notes

- Corpus rows are LongMemEval-S haystack sessions.
- Each corpus row is stored as one Lerim episode record.
- Latency measures local `ContextStore.search` with real hybrid retrieval.
- This is a local retrieval benchmark, not an HTTP daemon load test.
