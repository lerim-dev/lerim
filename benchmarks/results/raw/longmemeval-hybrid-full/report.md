# Lerim LongMemEval-S Retrieval-Only Benchmark

- Generated: `2026-05-19T07:18:55.849780+00:00`
- Command: `benchmarks/lerim_evidence/longmemeval.py --retrieval-mode hybrid --local-files-only --output-dir benchmarks/results/raw/longmemeval-hybrid-full`
- Retrieval mode: `hybrid`
- Dataset: `xiaowu0162/longmemeval-cleaned/longmemeval_s_cleaned.json`
- Dataset snapshot: `98d7416c24c778c2fee6e6f3006e7a073259d48f`
- Questions evaluated: `500`
- Full filtered run: `True`
- LLM in loop: `False`

## Headline

| Metric | Value |
|---|---:|
| Recall any @ 1 | 82.2% |
| Recall any @ 3 | 93.4% |
| Recall any @ 5 | 96.4% |
| Recall any @ 10 | 98.6% |
| Recall any @ 20 | 99.4% |
| NDCG @ 10 | 88.6% |
| MRR | 88.4% |
| Retrieval p50 | 7.82 ms |
| Retrieval p95 | 8.55 ms |
| Indexing p50 | 1403.82 ms |

## By Question Type

| Type | Count | R@5 | R@10 | R@20 | MRR |
|---|---:|---:|---:|---:|---:|
| knowledge-update | 78 | 100.0% | 100.0% | 100.0% | 92.9% |
| multi-session | 133 | 97.7% | 100.0% | 100.0% | 93.1% |
| single-session-assistant | 56 | 100.0% | 100.0% | 100.0% | 97.3% |
| single-session-preference | 30 | 86.7% | 93.3% | 93.3% | 75.3% |
| single-session-user | 70 | 92.9% | 97.1% | 100.0% | 75.9% |
| temporal-reasoning | 133 | 95.5% | 97.7% | 99.2% | 86.8% |

## Methodology Notes

- This is retrieval-only, not the official LongMemEval QA score.
- Each question builds a fresh Lerim SQLite context store.
- Each haystack session becomes one Lerim `episode` record.
- Raw predictions are saved in `predictions.jsonl`.
