"""Measure Lerim retrieval latency on LongMemEval-S sessions."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lerim.context import ContextStore, ProjectIdentity

try:
    from benchmarks.lerim_evidence.longmemeval import (
        DATASET_FILENAME,
        DATASET_REPO_ID,
        _bounded_text,
        _safe_id,
        build_run_metadata,
        chunk_session_to_text,
        episode_fields_from_transcript,
        filter_entries,
        load_dataset,
        nearest_rank_percentile,
        resolve_dataset_path,
    )
except ModuleNotFoundError:
    sys.path.append(str(Path(__file__).resolve().parents[2]))
    from benchmarks.lerim_evidence.longmemeval import (
        DATASET_FILENAME,
        DATASET_REPO_ID,
        _bounded_text,
        _safe_id,
        build_run_metadata,
        chunk_session_to_text,
        episode_fields_from_transcript,
        filter_entries,
        load_dataset,
        nearest_rank_percentile,
        resolve_dataset_path,
    )


@dataclass(frozen=True)
class CorpusRow:
    """One session transcript row used for latency seeding."""

    row_id: str
    question_id: str
    session_id: str
    transcript: str
    turn_count: int
    started_at: str


def _timestamp_for_path() -> str:
    """Return a compact UTC timestamp for default output folders."""
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def parse_sizes(raw: str) -> list[int]:
    """Parse comma-separated corpus sizes."""
    sizes: list[int] = []
    for item in str(raw or "").split(","):
        text = item.strip()
        if not text:
            continue
        value = int(text)
        if value <= 0:
            raise ValueError(f"invalid_size:{value}")
        sizes.append(value)
    if not sizes:
        raise ValueError("at_least_one_size_required")
    return sorted(set(sizes))


def build_corpus_rows(entries: list[Any], *, max_rows: int) -> list[CorpusRow]:
    """Build real corpus rows from LongMemEval haystack sessions."""
    rows: list[CorpusRow] = []
    for entry in entries:
        for index, session_id in enumerate(entry.haystack_session_ids):
            turns = entry.haystack_sessions[index]
            transcript = chunk_session_to_text(turns)
            if not transcript:
                continue
            rows.append(
                CorpusRow(
                    row_id=f"{entry.question_id}_{index:03d}_{_safe_id(session_id)}",
                    question_id=entry.question_id,
                    session_id=session_id,
                    transcript=transcript,
                    turn_count=len(turns),
                    started_at=entry.haystack_dates[index],
                )
            )
            if len(rows) >= max_rows:
                return rows
    return rows


def _seed_store(rows: list[CorpusRow], work_dir: Path) -> tuple[ContextStore, ProjectIdentity]:
    """Seed one ContextStore with real LongMemEval session rows."""
    repo = work_dir / "repo"
    repo.mkdir(parents=True)
    (repo / ".git").mkdir()
    identity = ProjectIdentity(
        project_id=f"proj_latency_{len(rows)}",
        project_slug=f"latency-{len(rows)}",
        repo_path=repo,
    )
    store = ContextStore(work_dir / "context.sqlite3")
    store.register_project(identity)
    original_refresh = store._refresh_derived_indexes_after_write

    def _skip_index_refresh(*, record_ids: list[str], **_kwargs: Any) -> None:
        """Skip per-record refresh while seeding a benchmark corpus."""
        del record_ids

    created_record_ids: list[str] = []
    store._refresh_derived_indexes_after_write = _skip_index_refresh  # type: ignore[method-assign]
    try:
        for index, row in enumerate(rows):
            session_id = f"{row.session_id}__latency_row_{index:06d}"
            source_trace_ref = f"longmemeval:{row.question_id}:{row.session_id}"
            store.upsert_session(
                project_id=identity.project_id,
                session_id=session_id,
                agent_type="longmemeval-latency",
                source_trace_ref=source_trace_ref,
                repo_path=str(repo),
                cwd=str(repo),
                started_at=row.started_at,
                model_name=None,
                instructions_text=None,
                prompt_text=None,
                source_name="longmemeval",
                source_profile="coding-agent",
            )
            fields = episode_fields_from_transcript(
                transcript=row.transcript,
                session_id=row.session_id,
                turn_count=row.turn_count,
            )
            record_id = f"rec_latency_{index:06d}_{_safe_id(row.row_id)}"
            store.create_record(
                project_id=identity.project_id,
                session_id=session_id,
                kind="episode",
                title=_bounded_text(f"LongMemEval session {row.session_id}", 120),
                body=fields["body"],
                user_intent=fields["user_intent"],
                what_happened=fields["what_happened"],
                outcomes=fields["outcomes"],
                record_id=record_id,
                source_name="longmemeval",
                source_profile="coding-agent",
                source_event_refs=[source_trace_ref],
                evidence_refs=[source_trace_ref],
                index_text=row.transcript,
            )
            created_record_ids.append(record_id)
    finally:
        store._refresh_derived_indexes_after_write = original_refresh  # type: ignore[method-assign]
    original_refresh(record_ids=created_record_ids)
    return store, identity


def _measure_queries(
    *,
    store: ContextStore,
    project_id: str,
    queries: list[str],
    iterations: int,
    retrieval_limit: int,
) -> list[dict[str, Any]]:
    """Measure repeated ContextStore.search calls."""
    rows: list[dict[str, Any]] = []
    for iteration in range(iterations):
        for query_index, query in enumerate(queries):
            started = time.perf_counter()
            hits = store.search(
                project_ids=[project_id],
                query=query,
                kind_filters=["episode"],
                statuses=["active"],
                include_archived=False,
                limit=retrieval_limit,
            )
            rows.append(
                {
                    "iteration": iteration,
                    "query_index": query_index,
                    "latency_ms": (time.perf_counter() - started) * 1000,
                    "hit_count": len(hits),
                }
            )
    return rows


def summarize_latency(rows: list[dict[str, Any]]) -> dict[str, float | int]:
    """Summarize latency rows."""
    samples = [float(row["latency_ms"]) for row in rows]
    hit_counts = [int(row["hit_count"]) for row in rows]
    return {
        "ops": len(rows),
        "p50_ms": nearest_rank_percentile(samples, 50),
        "p90_ms": nearest_rank_percentile(samples, 90),
        "p95_ms": nearest_rank_percentile(samples, 95),
        "p99_ms": nearest_rank_percentile(samples, 99),
        "min_ms": min(samples) if samples else 0.0,
        "max_ms": max(samples) if samples else 0.0,
        "avg_ms": statistics.fmean(samples) if samples else 0.0,
        "avg_hit_count": statistics.fmean(hit_counts) if hit_counts else 0.0,
    }


def render_markdown(report: dict[str, Any]) -> str:
    """Render latency results as Markdown."""
    lines = [
        "# Lerim Retrieval Latency Benchmark",
        "",
        f"- Generated: `{report['generated_at']}`",
        f"- Command: `{report.get('command', '')}`",
        f"- Dataset snapshot: `{report['dataset']['snapshot'] or report['dataset']['requested_revision']}`",
        f"- Queries: `{report['query_count']}`",
        f"- Iterations: `{report['iterations']}`",
        "",
        "| Corpus records | Ops | p50 | p90 | p99 | Avg hits |",
        "|---:|---:|---:|---:|---:|---:|",
    ]
    for size, payload in report["results"].items():
        lines.append(
            f"| {size} | {payload['ops']} | {payload['p50_ms']:.2f} ms | "
            f"{payload['p90_ms']:.2f} ms | {payload['p99_ms']:.2f} ms | "
            f"{payload['avg_hit_count']:.1f} |"
        )
    lines.extend(
        [
            "",
            "## Methodology Notes",
            "",
            "- Corpus rows are LongMemEval-S haystack sessions.",
            "- Each corpus row is stored as one Lerim episode record.",
            "- Latency measures local `ContextStore.search` with real hybrid retrieval.",
            "- This is a local retrieval benchmark, not an HTTP daemon load test.",
            "",
        ]
    )
    return "\n".join(lines)


def write_outputs(report: dict[str, Any], details: list[dict[str, Any]], output_dir: Path) -> None:
    """Write latency benchmark artifacts."""
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    lines = [json.dumps(row, sort_keys=True) for row in details]
    (output_dir / "details.jsonl").write_text(
        "\n".join(lines) + ("\n" if lines else ""),
        encoding="utf-8",
    )
    (output_dir / "report.md").write_text(render_markdown(report), encoding="utf-8")


def run_benchmark(args: argparse.Namespace) -> Path:
    """Run the retrieval latency benchmark."""
    started_at = time.perf_counter()
    dataset_path = resolve_dataset_path(args)
    raw_entries = load_dataset(dataset_path)
    filtered_entries, abstention_excluded_count = filter_entries(
        raw_entries,
        question_type=None,
    )
    sizes = parse_sizes(args.sizes)
    queries = [entry.question for entry in filtered_entries[: args.query_count]]
    corpus_rows = build_corpus_rows(filtered_entries, max_rows=max(sizes))
    if len(corpus_rows) < max(sizes):
        raise ValueError(f"not_enough_real_corpus_rows:{len(corpus_rows)}:{max(sizes)}")

    results: dict[str, Any] = {}
    details: list[dict[str, Any]] = []
    for size in sizes:
        with tempfile.TemporaryDirectory(prefix=f"lerim-latency-{size}-") as raw_work_dir:
            store, identity = _seed_store(corpus_rows[:size], Path(raw_work_dir))
            rows = _measure_queries(
                store=store,
                project_id=identity.project_id,
                queries=queries,
                iterations=args.iterations,
                retrieval_limit=args.retrieval_limit,
            )
        for row in rows:
            row["corpus_records"] = size
        details.extend(rows)
        results[str(size)] = summarize_latency(rows)
        print(
            f"[{size}] p50={results[str(size)]['p50_ms']:.2f}ms "
            f"p99={results[str(size)]['p99_ms']:.2f}ms",
            flush=True,
        )

    metadata = build_run_metadata(
        args=args,
        dataset_path=dataset_path,
        raw_entries_count=len(raw_entries),
        filtered_entries_count=len(filtered_entries),
        evaluated_count=len(queries),
        abstention_excluded_count=abstention_excluded_count,
    )
    report = {
        **metadata,
        "benchmark": "longmemeval_s_retrieval_latency",
        "query_count": len(queries),
        "iterations": args.iterations,
        "sizes": sizes,
        "runtime": {
            "wall_clock_ms": (time.perf_counter() - started_at) * 1000,
            "failure_count": 0,
        },
        "results": results,
    }
    output_dir = args.output_dir
    if output_dir is None:
        output_dir = Path("benchmarks/results/raw") / f"retrieval-latency-{_timestamp_for_path()}"
    output_dir = output_dir.expanduser().resolve()
    write_outputs(report, details, output_dir)
    return output_dir


def parse_args() -> argparse.Namespace:
    """Parse retrieval latency CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Measure local Lerim retrieval latency on LongMemEval sessions.",
    )
    parser.add_argument("--dataset-path", type=Path, default=None)
    parser.add_argument("--dataset-repo", default=DATASET_REPO_ID)
    parser.add_argument("--dataset-file", default=DATASET_FILENAME)
    parser.add_argument("--dataset-revision", default=None)
    parser.add_argument("--local-files-only", action="store_true")
    parser.add_argument("--sizes", default="100,1000")
    parser.add_argument("--query-count", type=int, default=25)
    parser.add_argument("--iterations", type=int, default=3)
    parser.add_argument("--retrieval-limit", type=int, default=20)
    parser.add_argument("--retrieval-mode", default="hybrid")
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--question-type", default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    return parser.parse_args()


def main() -> None:
    """Run the retrieval latency benchmark from the command line."""
    output_dir = run_benchmark(parse_args())
    print(f"Retrieval latency report written to {output_dir}")


if __name__ == "__main__":
    main()
