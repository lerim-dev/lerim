# Lerim Context Budget Benchmark

- Generated: `2026-05-19T07:31:56.288860+00:00`
- Command: `benchmarks/scripts/run_context_budget_full.py --local-files-only --progress-every 25 --output-dir benchmarks/results/raw/context-budget-hybrid-full`
- Dataset snapshot: `98d7416c24c778c2fee6e6f3006e7a073259d48f`
- Questions evaluated: `500`
- Tokenizer: `mixedbread-ai/mxbai-embed-xsmall-v1`
- Retrieval mode: `hybrid`
- Full filtered run: `True`

## Headline

| Window | Avg selected tokens | Avg tokens reduced | Avg reduction | Recall any |
|---|---:|---:|---:|---:|
| Top 1 | 2985 | 107342 | 97.3% | 82.2% |
| Top 3 | 8810 | 101516 | 92.0% | 93.4% |
| Top 5 | 14217 | 96109 | 87.1% | 96.4% |
| Top 10 | 27346 | 82981 | 75.2% | 98.6% |
| Top 20 | 52583 | 57744 | 52.3% | 99.4% |

## Methodology Notes

- Full replay tokens count every LongMemEval-S haystack session transcript.
- Selected tokens count the raw transcripts for Lerim's retrieved top-K sessions.
- Counts use a Hugging Face tokenizer, not character division.
- This is a retrieval-window benchmark, not a context-brief quality score.
