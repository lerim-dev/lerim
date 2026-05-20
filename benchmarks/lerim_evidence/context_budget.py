"""Run Lerim's real-data context-budget benchmark.

The benchmark uses LongMemEval-S haystacks instead of synthetic memories. It
measures how many tokenizer tokens are needed when replaying all haystack
sessions versus only the top-K sessions retrieved by Lerim.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from huggingface_hub import snapshot_download
from tokenizers import Tokenizer

from lerim.config.settings import get_config

try:
    from benchmarks.lerim_evidence.longmemeval import (
        DEFAULT_RETRIEVAL_LIMIT,
        DATASET_FILENAME,
        DATASET_REPO_ID,
        METRIC_K_VALUES,
        build_run_metadata,
        chunk_session_to_text,
        filter_entries,
        load_dataset,
        recall_any,
        resolve_dataset_path,
        run_question,
    )
except ModuleNotFoundError:
    sys.path.append(str(Path(__file__).resolve().parents[2]))
    from benchmarks.lerim_evidence.longmemeval import (
        DEFAULT_RETRIEVAL_LIMIT,
        DATASET_FILENAME,
        DATASET_REPO_ID,
        METRIC_K_VALUES,
        build_run_metadata,
        chunk_session_to_text,
        filter_entries,
        load_dataset,
        recall_any,
        resolve_dataset_path,
        run_question,
    )


def _utc_timestamp_for_path() -> str:
    """Return a compact UTC timestamp suitable for artifact paths."""
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _load_tokenizer(model_id: str | None) -> tuple[Tokenizer, str]:
    """Load a Hugging Face tokenizer for benchmark-grade token counts."""
    config = get_config()
    tokenizer_model = str(model_id or config.embedding_model_id).strip()
    model_dir = snapshot_download(
        repo_id=tokenizer_model,
        allow_patterns=["tokenizer.json", "tokenizer_config.json", "special_tokens_map.json"],
    )
    tokenizer_path = Path(model_dir) / "tokenizer.json"
    if not tokenizer_path.exists():
        raise RuntimeError(f"tokenizer_json_not_found:{tokenizer_model}")
    tokenizer = Tokenizer.from_file(str(tokenizer_path))
    tokenizer.no_truncation()
    tokenizer.no_padding()
    return tokenizer, tokenizer_model


def count_tokens(tokenizer: Tokenizer, text: str) -> int:
    """Count tokenizer tokens for one text without heuristic char division."""
    return len(tokenizer.encode(str(text or "")).ids)


def context_reduction_ratio(*, full_tokens: int, selected_tokens: int) -> float:
    """Return the fraction of full replay tokens avoided by selected context."""
    if full_tokens <= 0:
        return 0.0
    return max(0.0, 1.0 - (selected_tokens / full_tokens))


def _session_token_counts(entry: Any, tokenizer: Tokenizer) -> dict[str, int]:
    """Count tokens for every haystack session transcript in one entry."""
    counts: dict[str, int] = {}
    for session_id, turns in zip(entry.haystack_session_ids, entry.haystack_sessions, strict=True):
        counts[session_id] = count_tokens(tokenizer, chunk_session_to_text(turns))
    return counts


def _score_question(
    *,
    entry: Any,
    tokenizer: Tokenizer,
    retrieval_mode: str,
    retrieval_limit: int,
    batch_indexing: bool,
) -> dict[str, Any]:
    """Run retrieval for one question and compute context budget at each K."""
    result = run_question(
        entry=entry,
        retrieval_mode=retrieval_mode,
        retrieval_limit=retrieval_limit,
        batch_indexing=batch_indexing,
    )
    session_tokens = _session_token_counts(entry, tokenizer)
    full_tokens = sum(session_tokens.values())
    selected_by_k: dict[str, dict[str, float | int]] = {}
    for k in METRIC_K_VALUES:
        top_ids = result.retrieved_session_ids[:k]
        selected_tokens = sum(session_tokens.get(session_id, 0) for session_id in top_ids)
        selected_by_k[f"top_{k}"] = {
            "selected_tokens": selected_tokens,
            "tokens_reduced": max(0, full_tokens - selected_tokens),
            "reduction_ratio": context_reduction_ratio(
                full_tokens=full_tokens,
                selected_tokens=selected_tokens,
            ),
            "recall_any": recall_any(top_ids, result.gold_session_ids, k),
        }
    return {
        "question_id": result.question_id,
        "question_type": result.question_type,
        "haystack_session_count": result.haystack_session_count,
        "full_haystack_tokens": full_tokens,
        "indexed_character_count": result.indexed_character_count,
        "retrieval_ms": result.retrieval_ms,
        "indexing_ms": result.indexing_ms,
        "retrieved_session_ids": result.retrieved_session_ids,
        "gold_session_ids": result.gold_session_ids,
        "selected_by_k": selected_by_k,
    }


def _mean(values: list[float]) -> float:
    """Return the arithmetic mean, or zero for an empty list."""
    return sum(values) / len(values) if values else 0.0


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate per-question context-budget rows."""
    by_type: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_type.setdefault(str(row["question_type"]), []).append(row)

    def summarize_group(items: list[dict[str, Any]]) -> dict[str, Any]:
        """Summarize one result group."""
        payload: dict[str, Any] = {
            "count": len(items),
            "avg_full_haystack_tokens": _mean(
                [float(item["full_haystack_tokens"]) for item in items]
            ),
        }
        for k in METRIC_K_VALUES:
            key = f"top_{k}"
            payload[key] = {
                "avg_selected_tokens": _mean(
                    [float(item["selected_by_k"][key]["selected_tokens"]) for item in items]
                ),
                "avg_tokens_reduced": _mean(
                    [float(item["selected_by_k"][key]["tokens_reduced"]) for item in items]
                ),
                "avg_reduction_ratio": _mean(
                    [float(item["selected_by_k"][key]["reduction_ratio"]) for item in items]
                ),
                "recall_any": _mean(
                    [float(item["selected_by_k"][key]["recall_any"]) for item in items]
                ),
            }
        return payload

    return {
        "headline": summarize_group(rows),
        "per_type": {
            question_type: summarize_group(items)
            for question_type, items in sorted(by_type.items(), key=lambda item: item[0])
        },
        "per_question": rows,
    }


def _format_percent(value: float) -> str:
    """Format a ratio as a percentage string."""
    return f"{value * 100:.1f}%"


def render_markdown(report: dict[str, Any]) -> str:
    """Render a context-budget report as Markdown."""
    headline = report["results"]["headline"]
    lines = [
        "# Lerim Context Budget Benchmark",
        "",
        f"- Generated: `{report['generated_at']}`",
        f"- Command: `{report.get('command', '')}`",
        f"- Dataset snapshot: `{report['dataset']['snapshot'] or report['dataset']['requested_revision']}`",
        f"- Questions evaluated: `{report['dataset']['evaluated_entries']}`",
        f"- Tokenizer: `{report['tokenizer']['model_id']}`",
        f"- Retrieval mode: `{report['retrieval_mode']}`",
        f"- Full filtered run: `{report['is_full_filtered_run']}`",
        "",
        "## Headline",
        "",
        "| Window | Avg selected tokens | Avg tokens reduced | Avg reduction | Recall any |",
        "|---|---:|---:|---:|---:|",
    ]
    for k in METRIC_K_VALUES:
        key = f"top_{k}"
        item = headline[key]
        lines.append(
            "| "
            f"Top {k} | {item['avg_selected_tokens']:.0f} | "
            f"{item['avg_tokens_reduced']:.0f} | "
            f"{_format_percent(item['avg_reduction_ratio'])} | "
            f"{_format_percent(item['recall_any'])} |"
        )
    lines.extend(
        [
            "",
            "## Methodology Notes",
            "",
            "- Full replay tokens count every LongMemEval-S haystack session transcript.",
            "- Selected tokens count the raw transcripts for Lerim's retrieved top-K sessions.",
            "- Counts use a Hugging Face tokenizer, not character division.",
            "- This is a retrieval-window benchmark, not a context-brief quality score.",
            "",
        ]
    )
    return "\n".join(lines)


def write_outputs(report: dict[str, Any], output_dir: Path) -> None:
    """Write context-budget benchmark artifacts."""
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    lines = [
        json.dumps(row, sort_keys=True)
        for row in report["results"]["per_question"]
    ]
    (output_dir / "predictions.jsonl").write_text(
        "\n".join(lines) + ("\n" if lines else ""),
        encoding="utf-8",
    )
    (output_dir / "report.md").write_text(render_markdown(report), encoding="utf-8")


def run_benchmark(args: argparse.Namespace) -> Path:
    """Run the real-data context-budget benchmark."""
    started_at = time.perf_counter()
    dataset_path = resolve_dataset_path(args)
    raw_entries = load_dataset(dataset_path)
    filtered_entries, abstention_excluded_count = filter_entries(
        raw_entries,
        question_type=args.question_type,
    )
    start = max(0, int(args.offset))
    stop = None if args.limit is None else start + max(0, int(args.limit))
    evaluated_entries = filtered_entries[start:stop]
    if not evaluated_entries:
        raise ValueError("context_budget_slice_is_empty")

    tokenizer, tokenizer_model = _load_tokenizer(args.tokenizer_model)
    rows: list[dict[str, Any]] = []
    for index, entry in enumerate(evaluated_entries, start=1):
        rows.append(
            _score_question(
                entry=entry,
                tokenizer=tokenizer,
                retrieval_mode=args.retrieval_mode,
                retrieval_limit=args.retrieval_limit,
                batch_indexing=args.batch_indexing,
            )
        )
        if args.progress_every and index % args.progress_every == 0:
            top_10 = summarize(rows)["headline"]["top_10"]
            print(
                f"[{index}/{len(evaluated_entries)}] "
                f"top10_reduction={_format_percent(top_10['avg_reduction_ratio'])}",
                flush=True,
            )

    metadata = build_run_metadata(
        args=args,
        dataset_path=dataset_path,
        raw_entries_count=len(raw_entries),
        filtered_entries_count=len(filtered_entries),
        evaluated_count=len(evaluated_entries),
        abstention_excluded_count=abstention_excluded_count,
    )
    report = {
        **metadata,
        "benchmark": "longmemeval_s_context_budget",
        "tokenizer": {
            "model_id": tokenizer_model,
            "truncation": "disabled",
            "padding": "disabled",
        },
        "runtime": {
            "wall_clock_ms": (time.perf_counter() - started_at) * 1000,
            "failure_count": 0,
        },
        "results": summarize(rows),
    }
    output_dir = args.output_dir
    if output_dir is None:
        output_dir = Path("benchmarks/results/raw") / f"context-budget-{_utc_timestamp_for_path()}"
    output_dir = output_dir.expanduser().resolve()
    write_outputs(report, output_dir)
    return output_dir


def parse_args() -> argparse.Namespace:
    """Parse context-budget benchmark CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Run Lerim's real-data context-budget benchmark.",
    )
    parser.add_argument("--dataset-path", type=Path, default=None)
    parser.add_argument("--dataset-repo", default=DATASET_REPO_ID)
    parser.add_argument("--dataset-file", default=DATASET_FILENAME)
    parser.add_argument("--dataset-revision", default=None)
    parser.add_argument("--local-files-only", action="store_true")
    parser.add_argument(
        "--retrieval-mode",
        choices=("hybrid", "lexical"),
        default="hybrid",
    )
    parser.add_argument("--retrieval-limit", type=int, default=DEFAULT_RETRIEVAL_LIMIT)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--question-type", default=None)
    parser.add_argument("--tokenizer-model", default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--progress-every", type=int, default=10)
    parser.add_argument(
        "--no-batch-indexing",
        dest="batch_indexing",
        action="store_false",
        help="Refresh derived indexes after every record write instead of once per question.",
    )
    parser.set_defaults(batch_indexing=True)
    return parser.parse_args()


def main() -> None:
    """Run the context-budget benchmark from the command line."""
    output_dir = run_benchmark(parse_args())
    print(f"Context-budget report written to {output_dir}")


if __name__ == "__main__":
    main()
