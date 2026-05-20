"""Run Lerim's LongMemEval-S retrieval-only benchmark.

Each question builds a fresh index from its haystack sessions, retrieves top-K
sessions with the question text, and scores whether any gold answer session
appears in the retrieved set.

This is not the official LongMemEval QA metric. It is retrieval-only and has no
LLM judge in the loop.
"""

from __future__ import annotations

import argparse
import json
import math
import platform
import re
import statistics
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

from huggingface_hub import hf_hub_download

from lerim.config.settings import get_config
from lerim.context import ContextStore, ProjectIdentity
from lerim.context import retrieval
from lerim.context.spec import (
    MAX_EPISODE_BODY_CHARS,
    MAX_EPISODE_OUTCOMES_CHARS,
    MAX_EPISODE_USER_INTENT_CHARS,
    MAX_EPISODE_WHAT_HAPPENED_CHARS,
)

DATASET_REPO_ID = "xiaowu0162/longmemeval-cleaned"
DATASET_FILENAME = "longmemeval_s_cleaned.json"
ABSTENTION_TYPES = {
    "single-session-user_abs",
    "multi-session_abs",
    "knowledge-update_abs",
    "temporal-reasoning_abs",
}
METRIC_K_VALUES = (1, 3, 5, 10, 20)
DEFAULT_RETRIEVAL_LIMIT = 20


@dataclass(frozen=True)
class LongMemEvalEntry:
    """One LongMemEval-S retrieval entry."""

    question_id: str
    question_type: str
    question: str
    question_date: str
    answer: str
    answer_session_ids: list[str]
    haystack_dates: list[str]
    haystack_session_ids: list[str]
    haystack_sessions: list[list[dict[str, Any]]]


@dataclass(frozen=True)
class RetrievedSession:
    """One retrieved session plus retrieval metadata."""

    session_id: str
    record_id: str
    rank: int
    score: float
    sources: list[str]


@dataclass(frozen=True)
class QuestionResult:
    """Scored result for one LongMemEval-S question."""

    question_id: str
    question_type: str
    haystack_session_count: int
    gold_session_ids: list[str]
    retrieved_session_ids: list[str]
    retrieved: list[dict[str, Any]]
    recall_any_at_1: float
    recall_any_at_3: float
    recall_any_at_5: float
    recall_any_at_10: float
    recall_any_at_20: float
    ndcg_at_10: float
    mrr: float
    indexing_ms: float
    retrieval_ms: float
    indexed_character_count: int


def _utc_now() -> str:
    """Return the current UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


def _safe_id(value: str) -> str:
    """Return a stable identifier safe for Lerim record and project ids."""
    text = re.sub(r"[^A-Za-z0-9_]+", "_", str(value or "").strip())
    return text.strip("_") or "unknown"


def _bounded_text(text: str, max_chars: int) -> str:
    """Fit text into one bounded schema field without phrase-specific logic."""
    normalized = str(text or "").strip()
    if len(normalized) <= max_chars:
        return normalized
    marker = "\n[...]\n"
    if max_chars <= len(marker) + 2:
        return normalized[:max_chars].strip()
    head_chars = max(1, (max_chars - len(marker)) // 2)
    tail_chars = max_chars - len(marker) - head_chars
    return f"{normalized[:head_chars].rstrip()}{marker}{normalized[-tail_chars:].lstrip()}"


def chunk_session_to_text(turns: list[dict[str, Any]]) -> str:
    """Convert one haystack session into role/content transcript text."""
    lines: list[str] = []
    for turn in turns:
        role = str(turn.get("role") or "unknown").strip() or "unknown"
        content = str(turn.get("content") or "").strip()
        if content:
            lines.append(f"{role}: {content}")
    return "\n".join(lines).strip()


def episode_fields_from_transcript(
    *,
    transcript: str,
    session_id: str,
    turn_count: int,
) -> dict[str, str]:
    """Map raw transcript text into Lerim's bounded episode record schema."""
    text = str(transcript or "").strip() or "Empty LongMemEval haystack session."
    user_intent = _bounded_text(
        f"Index LongMemEval haystack session {session_id} for retrieval-only evaluation.",
        MAX_EPISODE_USER_INTENT_CHARS,
    )
    return {
        "body": _bounded_text(text, MAX_EPISODE_BODY_CHARS),
        "user_intent": user_intent,
        "what_happened": _bounded_text(text, MAX_EPISODE_WHAT_HAPPENED_CHARS),
        "outcomes": _bounded_text(f"turn_count={turn_count}", MAX_EPISODE_OUTCOMES_CHARS),
    }


def recall_any(retrieved_session_ids: list[str], gold_session_ids: list[str], k: int) -> float:
    """Return 1.0 when any gold session is found in top-k retrieved sessions."""
    top_k = set(retrieved_session_ids[:k])
    return 1.0 if any(gold_id in top_k for gold_id in gold_session_ids) else 0.0


def dcg(relevances: list[bool], k: int) -> float:
    """Compute discounted cumulative gain over boolean relevances."""
    total = 0.0
    for index, relevant in enumerate(relevances[:k]):
        total += (1.0 if relevant else 0.0) / math.log2(index + 2)
    return total


def ndcg(retrieved_session_ids: list[str], gold_session_ids: set[str], k: int) -> float:
    """Compute normalized discounted cumulative gain at k."""
    relevances = [session_id in gold_session_ids for session_id in retrieved_session_ids[:k]]
    ideal_relevances = [True] * min(k, len(gold_session_ids))
    ideal = dcg(ideal_relevances, k)
    if ideal == 0:
        return 0.0
    return dcg(relevances, k) / ideal


def mrr(retrieved_session_ids: list[str], gold_session_ids: set[str]) -> float:
    """Compute mean reciprocal rank for one question."""
    for index, session_id in enumerate(retrieved_session_ids, start=1):
        if session_id in gold_session_ids:
            return 1.0 / index
    return 0.0


def nearest_rank_percentile(samples: list[float], percentile: float) -> float:
    """Return a nearest-rank percentile value."""
    if not samples:
        return 0.0
    ordered = sorted(samples)
    rank = max(1, math.ceil((percentile / 100.0) * len(ordered)))
    return ordered[min(rank - 1, len(ordered) - 1)]


def _mean(values: list[float]) -> float:
    """Return the arithmetic mean, or zero for an empty list."""
    if not values:
        return 0.0
    return statistics.fmean(values)


def load_dataset(path: Path) -> list[LongMemEvalEntry]:
    """Load and validate LongMemEval-S entries from one JSON file."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("longmemeval_payload_must_be_list")
    entries: list[LongMemEvalEntry] = []
    for index, item in enumerate(payload):
        if not isinstance(item, dict):
            raise ValueError(f"longmemeval_entry_must_be_object:{index}")
        required = (
            "question_id",
            "question_type",
            "question",
            "question_date",
            "answer",
            "answer_session_ids",
            "haystack_dates",
            "haystack_session_ids",
            "haystack_sessions",
        )
        missing = [field for field in required if field not in item]
        if missing:
            raise ValueError(f"longmemeval_entry_missing_fields:{index}:{','.join(missing)}")
        _validate_list_field(item, index=index, field="answer_session_ids")
        haystack_dates = _validate_list_field(item, index=index, field="haystack_dates")
        haystack_session_ids = _validate_list_field(
            item,
            index=index,
            field="haystack_session_ids",
        )
        haystack_sessions = _validate_list_field(item, index=index, field="haystack_sessions")
        if not (
            len(haystack_dates)
            == len(haystack_session_ids)
            == len(haystack_sessions)
        ):
            raise ValueError(f"longmemeval_entry_haystack_length_mismatch:{index}")
        for session_index, session in enumerate(haystack_sessions):
            if not isinstance(session, list):
                raise ValueError(
                    f"longmemeval_entry_haystack_session_must_be_list:{index}:{session_index}"
                )
        entries.append(
            LongMemEvalEntry(
                question_id=str(item["question_id"]),
                question_type=str(item["question_type"]),
                question=str(item["question"]),
                question_date=str(item["question_date"]),
                answer=str(item["answer"]),
                answer_session_ids=[str(value) for value in item["answer_session_ids"]],
                haystack_dates=[str(value) for value in item["haystack_dates"]],
                haystack_session_ids=[str(value) for value in item["haystack_session_ids"]],
                haystack_sessions=list(item["haystack_sessions"]),
            )
        )
    return entries


def _validate_list_field(item: dict[str, Any], *, index: int, field: str) -> list[Any]:
    """Return a list-valued field or fail with a precise dataset error."""
    value = item[field]
    if not isinstance(value, list):
        raise ValueError(f"longmemeval_entry_field_must_be_list:{index}:{field}")
    return value


def filter_entries(
    entries: list[LongMemEvalEntry],
    *,
    question_type: str | None,
) -> tuple[list[LongMemEvalEntry], int]:
    """Drop abstention entries and optionally keep one question type."""
    non_abstention = [entry for entry in entries if entry.question_type not in ABSTENTION_TYPES]
    if question_type:
        non_abstention = [entry for entry in non_abstention if entry.question_type == question_type]
    return non_abstention, len(entries) - len([entry for entry in entries if entry.question_type not in ABSTENTION_TYPES])


def resolve_dataset_path(args: argparse.Namespace) -> Path:
    """Resolve a dataset path from CLI args, downloading from Hugging Face when needed."""
    if args.dataset_path is not None:
        path = args.dataset_path.expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"dataset_path_not_found:{path}")
        return path
    downloaded = hf_hub_download(
        repo_id=args.dataset_repo,
        filename=args.dataset_file,
        repo_type="dataset",
        revision=args.dataset_revision,
        local_files_only=args.local_files_only,
    )
    return Path(downloaded).expanduser()


def _snapshot_from_dataset_path(path: Path) -> str | None:
    """Infer a Hugging Face snapshot commit from a cache path when available."""
    parts = path.parts
    if "snapshots" not in parts:
        return None
    index = parts.index("snapshots")
    if index + 1 >= len(parts):
        return None
    return parts[index + 1]


def _dataset_cache_ref(path: Path) -> str:
    """Return a public-safe dataset cache reference."""
    snapshot = _snapshot_from_dataset_path(path)
    if snapshot:
        return f"huggingface-cache:snapshots/{snapshot}/{path.name}"
    return "<local-dataset-path>"


def _git_value(args: list[str]) -> str | None:
    """Read one git value from the current checkout."""
    try:
        completed = subprocess.run(
            ["git", *args],
            check=True,
            cwd=Path(__file__).resolve().parents[2],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return completed.stdout.strip() or None


def _public_git_status(git_status: str | None) -> str:
    """Return a public-safe git status label for report metadata."""
    if not git_status:
        return ""
    return "<dirty worktree; rerun from clean commit before launch>"


def _lerim_version() -> str:
    """Return installed package version metadata when available."""
    try:
        return version("lerim")
    except PackageNotFoundError:
        return "editable"


def build_run_metadata(
    *,
    args: argparse.Namespace,
    dataset_path: Path,
    raw_entries_count: int,
    filtered_entries_count: int,
    evaluated_count: int,
    abstention_excluded_count: int,
) -> dict[str, Any]:
    """Build reproducibility metadata for one benchmark run."""
    config = get_config()
    git_status = _git_value(["status", "--short"])
    return {
        "schema_version": 1,
        "benchmark": "longmemeval_s_retrieval_only",
        "generated_at": _utc_now(),
        "retrieval_mode": args.retrieval_mode,
        "retrieval_limit": args.retrieval_limit,
        "batch_indexing": bool(getattr(args, "batch_indexing", True)),
        "offset": args.offset,
        "limit": args.limit,
        "question_type": args.question_type,
        "command": " ".join(sys.argv),
        "is_full_filtered_run": evaluated_count == filtered_entries_count
        and args.offset == 0
        and args.limit is None,
        "dataset": {
            "repo_id": args.dataset_repo,
            "filename": args.dataset_file,
            "requested_revision": args.dataset_revision,
            "cache_ref": _dataset_cache_ref(dataset_path),
            "snapshot": _snapshot_from_dataset_path(dataset_path),
            "raw_entries": raw_entries_count,
            "filtered_entries": filtered_entries_count,
            "evaluated_entries": evaluated_count,
            "abstention_excluded": abstention_excluded_count,
        },
        "methodology": {
            "retrieval_only": True,
            "llm_in_loop": False,
            "semantic_judge_in_loop": False,
            "official_longmemeval_qa_score": False,
            "index_unit": (
                "one compact Lerim episode record per haystack session, with "
                "hidden retrieval-only index_text containing the source session transcript"
            ),
            "gold_target": "answer_session_ids",
            "metric_k_values": list(METRIC_K_VALUES),
            "retrieval_compatible_metrics": [
                "recall_any_at_5",
                "recall_any_at_10",
                "recall_any_at_20",
                "ndcg_at_10",
                "mrr",
            ],
            "lerim_extra_metrics": ["recall_any_at_1", "recall_any_at_3", "latency"],
            "hybrid_fusion": {
                "method": "weighted_reciprocal_rank_fusion",
                "rrf_k": retrieval.RRF_K,
                "semantic_weight": retrieval.DEFAULT_SEMANTIC_RRF_WEIGHT,
                "lexical_weight": retrieval.DEFAULT_LEXICAL_RRF_WEIGHT,
            },
            "episode_schema_limits": {
                "body_chars": MAX_EPISODE_BODY_CHARS,
                "user_intent_chars": MAX_EPISODE_USER_INTENT_CHARS,
                "what_happened_chars": MAX_EPISODE_WHAT_HAPPENED_CHARS,
                "outcomes_chars": MAX_EPISODE_OUTCOMES_CHARS,
            },
        },
        "model_provider": {
            "llm_provider": "none",
            "llm_model": "none",
            "embedding_model": config.embedding_model_id,
        },
        "prompt_config_version": "not_applicable_retrieval_only",
        "cost_estimate": {
            "external_llm_usd": 0.0,
            "embedding_api_usd": 0.0,
            "notes": "Retrieval-only local embedding benchmark; no external LLM or embedding API calls.",
        },
        "environment": {
            "lerim_version": _lerim_version(),
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "hardware": {
                "platform": platform.platform(),
                "machine": platform.machine(),
                "processor": platform.processor(),
            },
            "git_commit": _git_value(["rev-parse", "HEAD"]),
            "git_dirty": bool(git_status),
            "git_status_short": _public_git_status(git_status),
        },
    }


def _create_store(work_dir: Path, entry: LongMemEvalEntry) -> tuple[ContextStore, ProjectIdentity]:
    """Create one fresh Lerim context store for a single LongMemEval question."""
    repo = work_dir / "repo"
    repo.mkdir(parents=True)
    (repo / ".git").mkdir()
    question_id = _safe_id(entry.question_id)
    identity = ProjectIdentity(
        project_id=f"proj_longmemeval_{question_id}",
        project_slug=f"longmemeval-{question_id}",
        repo_path=repo,
    )
    store = ContextStore(work_dir / "context.sqlite3")
    store.register_project(identity)
    return store, identity


def _seed_haystack(
    *,
    store: ContextStore,
    identity: ProjectIdentity,
    entry: LongMemEvalEntry,
    batch_indexing: bool,
    retrieval_mode: str,
) -> tuple[dict[str, str], int]:
    """Write one Lerim episode record per LongMemEval haystack session."""
    if not (
        len(entry.haystack_session_ids)
        == len(entry.haystack_sessions)
        == len(entry.haystack_dates)
    ):
        raise ValueError(f"haystack_length_mismatch:{entry.question_id}")

    record_to_session: dict[str, str] = {}
    indexed_character_count = 0
    created_record_ids: list[str] = []
    original_refresh = store._refresh_derived_indexes_after_write

    def _skip_index_refresh(*, record_ids: list[str], **_kwargs: Any) -> None:
        """Temporarily skip per-record derived index refresh during benchmark seeding."""
        del record_ids

    if batch_indexing:
        store._refresh_derived_indexes_after_write = _skip_index_refresh  # type: ignore[method-assign]
    try:
        for index, session_id in enumerate(entry.haystack_session_ids):
            turns = entry.haystack_sessions[index]
            transcript = chunk_session_to_text(turns)
            indexed_character_count += len(transcript)
            safe_session_id = _safe_id(session_id)
            lerim_session_id = f"{session_id}__longmemeval_row_{index:03d}"
            source_trace_ref = f"longmemeval:{entry.question_id}:{session_id}"
            store.upsert_session(
                project_id=identity.project_id,
                session_id=lerim_session_id,
                agent_type="longmemeval",
                source_trace_ref=source_trace_ref,
                repo_path=str(identity.repo_path),
                cwd=str(identity.repo_path),
                started_at=entry.haystack_dates[index],
                model_name=None,
                instructions_text=None,
                prompt_text=entry.question,
                source_name="longmemeval",
                source_profile="coding-agent",
            )
            fields = episode_fields_from_transcript(
                transcript=transcript,
                session_id=session_id,
                turn_count=len(turns),
            )
            record_id = f"rec_lme_{_safe_id(entry.question_id)}_{index:03d}_{safe_session_id}"
            store.create_record(
                project_id=identity.project_id,
                session_id=lerim_session_id,
                kind="episode",
                title=_bounded_text(f"LongMemEval session {session_id}", 120),
                body=fields["body"],
                user_intent=fields["user_intent"],
                what_happened=fields["what_happened"],
                outcomes=fields["outcomes"],
                record_id=record_id,
                source_name="longmemeval",
                source_profile="coding-agent",
                source_event_refs=[source_trace_ref],
                evidence_refs=[source_trace_ref],
                index_text=transcript,
            )
            record_to_session[record_id] = session_id
            created_record_ids.append(record_id)
    finally:
        if batch_indexing:
            store._refresh_derived_indexes_after_write = original_refresh  # type: ignore[method-assign]
    if batch_indexing:
        if retrieval_mode == "lexical":
            store._refresh_fts_after_write(record_ids=created_record_ids)
        else:
            original_refresh(record_ids=created_record_ids)
    return record_to_session, indexed_character_count


def _retrieve(
    *,
    store: ContextStore,
    project_id: str,
    query: str,
    retrieval_mode: str,
    retrieval_limit: int,
    record_to_session: dict[str, str],
) -> list[RetrievedSession]:
    """Retrieve candidate sessions from the seeded Lerim store."""
    if retrieval_mode == "hybrid":
        hits = store.search(
            project_ids=[project_id],
            query=query,
            kind_filters=["episode"],
            statuses=["active"],
            include_archived=False,
            limit=retrieval_limit,
        )
        rows = [
            (hit.record_id, hit.score, hit.sources)
            for hit in hits
            if hit.record_id in record_to_session
        ]
    elif retrieval_mode == "lexical":
        lexical_rows = retrieval.lexical_candidates(
            store,
            project_ids=[project_id],
            query=query,
            kind_filters=["episode"],
            statuses=["active"],
            valid_at=None,
            include_archived=False,
            limit=retrieval_limit,
        )
        rows = [
            (record_id, score, ["fts"])
            for record_id, score in lexical_rows
            if record_id in record_to_session
        ]
    else:
        raise ValueError(f"unsupported_retrieval_mode:{retrieval_mode}")

    return [
        RetrievedSession(
            session_id=record_to_session[record_id],
            record_id=record_id,
            rank=rank,
            score=float(score),
            sources=sources,
        )
        for rank, (record_id, score, sources) in enumerate(rows, start=1)
    ]


def run_question(
    *,
    entry: LongMemEvalEntry,
    retrieval_mode: str,
    retrieval_limit: int,
    batch_indexing: bool = True,
) -> QuestionResult:
    """Run and score one LongMemEval-S question against a fresh Lerim store."""
    with tempfile.TemporaryDirectory(prefix="lerim-longmemeval-") as raw_work_dir:
        store, identity = _create_store(Path(raw_work_dir), entry)
        indexing_started = time.perf_counter()
        record_to_session, indexed_character_count = _seed_haystack(
            store=store,
            identity=identity,
            entry=entry,
            batch_indexing=batch_indexing,
            retrieval_mode=retrieval_mode,
        )
        indexing_ms = (time.perf_counter() - indexing_started) * 1000
        retrieval_started = time.perf_counter()
        retrieved = _retrieve(
            store=store,
            project_id=identity.project_id,
            query=entry.question,
            retrieval_mode=retrieval_mode,
            retrieval_limit=retrieval_limit,
            record_to_session=record_to_session,
        )
        retrieval_ms = (time.perf_counter() - retrieval_started) * 1000

    retrieved_session_ids = [item.session_id for item in retrieved]
    gold_set = set(entry.answer_session_ids)
    return QuestionResult(
        question_id=entry.question_id,
        question_type=entry.question_type,
        haystack_session_count=len(entry.haystack_session_ids),
        gold_session_ids=entry.answer_session_ids,
        retrieved_session_ids=retrieved_session_ids,
        retrieved=[asdict(item) for item in retrieved],
        recall_any_at_1=recall_any(retrieved_session_ids, entry.answer_session_ids, 1),
        recall_any_at_3=recall_any(retrieved_session_ids, entry.answer_session_ids, 3),
        recall_any_at_5=recall_any(retrieved_session_ids, entry.answer_session_ids, 5),
        recall_any_at_10=recall_any(retrieved_session_ids, entry.answer_session_ids, 10),
        recall_any_at_20=recall_any(retrieved_session_ids, entry.answer_session_ids, 20),
        ndcg_at_10=ndcg(retrieved_session_ids, gold_set, 10),
        mrr=mrr(retrieved_session_ids, gold_set),
        indexing_ms=indexing_ms,
        retrieval_ms=retrieval_ms,
        indexed_character_count=indexed_character_count,
    )


def summarize_results(results: list[QuestionResult]) -> dict[str, Any]:
    """Summarize per-question results into headline and per-type metrics."""
    per_question = [asdict(result) for result in results]
    groups: dict[str, list[QuestionResult]] = {}
    for result in results:
        groups.setdefault(result.question_type, []).append(result)

    def metric_payload(items: list[QuestionResult]) -> dict[str, float | int]:
        """Aggregate standard retrieval and latency metrics for a result group."""
        retrieval_ms = [item.retrieval_ms for item in items]
        indexing_ms = [item.indexing_ms for item in items]
        return {
            "count": len(items),
            "recall_any_at_1": _mean([item.recall_any_at_1 for item in items]),
            "recall_any_at_3": _mean([item.recall_any_at_3 for item in items]),
            "recall_any_at_5": _mean([item.recall_any_at_5 for item in items]),
            "recall_any_at_10": _mean([item.recall_any_at_10 for item in items]),
            "recall_any_at_20": _mean([item.recall_any_at_20 for item in items]),
            "ndcg_at_10": _mean([item.ndcg_at_10 for item in items]),
            "mrr": _mean([item.mrr for item in items]),
            "indexing_p50_ms": nearest_rank_percentile(indexing_ms, 50),
            "indexing_p95_ms": nearest_rank_percentile(indexing_ms, 95),
            "indexing_p99_ms": nearest_rank_percentile(indexing_ms, 99),
            "retrieval_p50_ms": nearest_rank_percentile(retrieval_ms, 50),
            "retrieval_p95_ms": nearest_rank_percentile(retrieval_ms, 95),
            "retrieval_p99_ms": nearest_rank_percentile(retrieval_ms, 99),
        }

    return {
        "headline": metric_payload(results),
        "per_type": {
            question_type: metric_payload(items)
            for question_type, items in sorted(groups.items(), key=lambda item: item[0])
        },
        "per_question": per_question,
    }


def build_report(
    *,
    args: argparse.Namespace,
    dataset_path: Path,
    raw_entries: list[LongMemEvalEntry],
    filtered_entries: list[LongMemEvalEntry],
    evaluated_entries: list[LongMemEvalEntry],
    abstention_excluded_count: int,
    results: list[QuestionResult],
    failures: list[dict[str, Any]],
    started_at: float,
) -> dict[str, Any]:
    """Build the full JSON report payload for a benchmark run."""
    metadata = build_run_metadata(
        args=args,
        dataset_path=dataset_path,
        raw_entries_count=len(raw_entries),
        filtered_entries_count=len(filtered_entries),
        evaluated_count=len(evaluated_entries),
        abstention_excluded_count=abstention_excluded_count,
    )
    summary = summarize_results(results)
    return {
        **metadata,
        "runtime": {
            "wall_clock_ms": (time.perf_counter() - started_at) * 1000,
            "failure_count": len(failures),
        },
        "failures": failures,
        "results": summary,
    }


def _format_percent(value: float) -> str:
    """Format a metric value as a percentage string."""
    return f"{value * 100:.1f}%"


def render_markdown(report: dict[str, Any]) -> str:
    """Render a benchmark report as concise Markdown."""
    headline = report["results"]["headline"]
    lines = [
        "# Lerim LongMemEval-S Retrieval-Only Benchmark",
        "",
        f"- Generated: `{report['generated_at']}`",
        f"- Command: `{report.get('command', '')}`",
        f"- Retrieval mode: `{report['retrieval_mode']}`",
        f"- Dataset: `{report['dataset']['repo_id']}/{report['dataset']['filename']}`",
        f"- Dataset snapshot: `{report['dataset']['snapshot'] or report['dataset']['requested_revision']}`",
        f"- Questions evaluated: `{report['dataset']['evaluated_entries']}`",
        f"- Full filtered run: `{report['is_full_filtered_run']}`",
        f"- LLM in loop: `{report['methodology']['llm_in_loop']}`",
        "",
        "## Headline",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Recall any @ 1 | {_format_percent(headline['recall_any_at_1'])} |",
        f"| Recall any @ 3 | {_format_percent(headline['recall_any_at_3'])} |",
        f"| Recall any @ 5 | {_format_percent(headline['recall_any_at_5'])} |",
        f"| Recall any @ 10 | {_format_percent(headline['recall_any_at_10'])} |",
        f"| Recall any @ 20 | {_format_percent(headline['recall_any_at_20'])} |",
        f"| NDCG @ 10 | {_format_percent(headline['ndcg_at_10'])} |",
        f"| MRR | {_format_percent(headline['mrr'])} |",
        f"| Retrieval p50 | {headline['retrieval_p50_ms']:.2f} ms |",
        f"| Retrieval p95 | {headline['retrieval_p95_ms']:.2f} ms |",
        f"| Indexing p50 | {headline['indexing_p50_ms']:.2f} ms |",
        "",
        "## By Question Type",
        "",
        "| Type | Count | R@5 | R@10 | R@20 | MRR |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for question_type, payload in report["results"]["per_type"].items():
        lines.append(
            "| "
            f"{question_type} | {payload['count']} | "
            f"{_format_percent(payload['recall_any_at_5'])} | "
            f"{_format_percent(payload['recall_any_at_10'])} | "
            f"{_format_percent(payload['recall_any_at_20'])} | "
            f"{_format_percent(payload['mrr'])} |"
        )
    lines.extend(
        [
            "",
            "## Methodology Notes",
            "",
            "- This is retrieval-only, not the official LongMemEval QA score.",
            "- Each question builds a fresh Lerim SQLite context store.",
            "- Each haystack session becomes one Lerim `episode` record.",
            "- Raw predictions are saved in `predictions.jsonl`.",
            "",
        ]
    )
    return "\n".join(lines)


def write_outputs(report: dict[str, Any], output_dir: Path) -> None:
    """Write JSON, JSONL, and Markdown artifacts for a benchmark run."""
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    prediction_lines = [
        json.dumps(item, sort_keys=True)
        for item in report["results"]["per_question"]
    ]
    (output_dir / "predictions.jsonl").write_text(
        "\n".join(prediction_lines) + ("\n" if prediction_lines else ""),
        encoding="utf-8",
    )
    (output_dir / "report.md").write_text(render_markdown(report), encoding="utf-8")


def run_benchmark(args: argparse.Namespace) -> Path:
    """Run the LongMemEval-S benchmark and return the output directory."""
    started_at = time.perf_counter()
    dataset_path = resolve_dataset_path(args)
    raw_entries = load_dataset(dataset_path)
    filtered_entries, abstention_excluded_count = filter_entries(
        raw_entries,
        question_type=args.question_type,
    )
    if not filtered_entries:
        raise ValueError("no_longmemeval_entries_to_evaluate")
    start = max(0, int(args.offset))
    stop = None if args.limit is None else start + max(0, int(args.limit))
    evaluated_entries = filtered_entries[start:stop]
    if not evaluated_entries:
        raise ValueError("longmemeval_slice_is_empty")

    results: list[QuestionResult] = []
    failures: list[dict[str, Any]] = []
    total = len(evaluated_entries)
    for index, entry in enumerate(evaluated_entries, start=1):
        try:
            result = run_question(
                entry=entry,
                retrieval_mode=args.retrieval_mode,
                retrieval_limit=args.retrieval_limit,
                batch_indexing=args.batch_indexing,
            )
        except Exception as exc:
            failure = {
                "question_id": entry.question_id,
                "question_type": entry.question_type,
                "error": f"{type(exc).__name__}:{exc}",
            }
            failures.append(failure)
            if not args.continue_on_error:
                raise
        else:
            results.append(result)
        if args.progress_every and index % args.progress_every == 0:
            r5 = _mean([item.recall_any_at_5 for item in results])
            print(
                f"[{index}/{total}] R@5={_format_percent(r5)} "
                f"failures={len(failures)}",
                flush=True,
            )
    if not results:
        raise RuntimeError("longmemeval_no_successful_questions")

    report = build_report(
        args=args,
        dataset_path=dataset_path,
        raw_entries=raw_entries,
        filtered_entries=filtered_entries,
        evaluated_entries=evaluated_entries,
        abstention_excluded_count=abstention_excluded_count,
        results=results,
        failures=failures,
        started_at=started_at,
    )
    output_dir = args.output_dir
    if output_dir is None:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        output_dir = Path("benchmarks/results/raw") / f"longmemeval-{timestamp}"
    output_dir = output_dir.expanduser().resolve()
    write_outputs(report, output_dir)
    return output_dir


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for the LongMemEval-S runner."""
    parser = argparse.ArgumentParser(
        description="Run Lerim on LongMemEval-S retrieval-only scoring.",
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
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--progress-every", type=int, default=10)
    parser.add_argument("--continue-on-error", action="store_true")
    parser.add_argument(
        "--no-batch-indexing",
        dest="batch_indexing",
        action="store_false",
        help="Refresh derived indexes after every record write instead of once per question.",
    )
    parser.set_defaults(batch_indexing=True)
    return parser.parse_args()


def main() -> None:
    """Run the benchmark from the command line."""
    output_dir = run_benchmark(parse_args())
    print(f"LongMemEval-S report written to {output_dir}")


if __name__ == "__main__":
    main()
