"""Import aggregate Lerim extraction-quality benchmark results.

The full extraction eval can contain trace text, extracted record bodies, tool
payloads, case identifiers, and judge details. Public benchmark artifacts keep
aggregate metrics only, not private source material or per-case rows.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


BENCHMARK_ID = "lerim_extraction_quality_minimax_m27_full_47"
DEFAULT_SOURCE_REPORT = (
    Path(__file__).resolve().parents[3]
    / "lerim-cloud"
    / "evals"
    / "results"
    / "extraction_minimax_m27_full_47.json"
)
DEFAULT_OUTPUT_DIR = (
    Path("benchmarks")
    / "results"
    / "raw"
    / "extraction-minimax-m27-full-47"
)

HEADLINE_FIELDS: tuple[tuple[str, str], ...] = (
    ("task_completion_rate_pct", "Task completion"),
    ("quality_avg", "Quality average"),
    ("quality_gate_rate_pct", "Quality gate pass"),
    ("hard_gate_pass_rate_pct", "Hard gate pass"),
    ("concept_recall_avg", "Concept recall average"),
    ("required_concept_coverage_rate_pct", "Required concept coverage"),
    ("kind_alignment_rate_pct", "Kind alignment"),
    ("record_precision_avg", "Record precision average"),
    ("faithfulness_avg", "Faithfulness average"),
    ("claim_faithfulness_rate_pct", "Claim faithfulness"),
    ("negative_precision_rate_pct", "Negative precision"),
    ("signal_filtering_rate_pct", "Signal filtering"),
    ("evidence_coverage_rate_pct", "Evidence coverage"),
    ("evidence_validity_rate_pct", "Evidence validity"),
)

SUMMARY_FIELDS: tuple[str, ...] = (
    "framework",
    "task_completion_rate_pct",
    "record_budget_rate_pct",
    "episode_count_rate_pct",
    "episode_status_rate_pct",
    "episode_text_quality_rate_pct",
    "expected_kind_contract_rate_pct",
    "record_budget_contract_rate_pct",
    "concept_recall_avg",
    "required_concept_coverage_rate_pct",
    "kind_alignment_rate_pct",
    "negative_precision_rate_pct",
    "forbidden_concept_rate_avg",
    "signal_filtering_rate_pct",
    "scope_compatibility_rate_pct",
    "scope_semantics_rate_pct",
    "semantic_judge_coverage_rate_pct",
    "judge_completeness_rate_pct",
    "evidence_coverage_rate_pct",
    "evidence_validity_rate_pct",
    "judge_flag_cleanliness_rate_pct",
    "record_precision_avg",
    "faithfulness_avg",
    "claim_faithfulness_rate_pct",
    "standalone_quality_avg",
    "record_relevance_coverage_avg",
    "semantic_redundancy_rate_pct",
    "quality_gate_rate_pct",
    "hard_gate_pass_rate_pct",
    "quality_avg",
    "tool_call_errors_avg",
    "deterministic_diagnostic_avg",
    "dataset_case_count",
    "full_dataset_case_count",
    "dataset_coverage_rate_pct",
    "release_dataset_coverage_pass",
    "case_failures",
    "case_failure_rate_pct",
)


def _utc_now() -> str:
    """Return a UTC timestamp for report metadata."""
    return datetime.now(timezone.utc).isoformat()


def _git_value(args: list[str]) -> str | None:
    """Read one git value from the local checkout."""
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=Path(__file__).resolve().parents[2],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return completed.stdout.strip() or None


def _public_git_status(git_status: str | None) -> str:
    """Return a public-safe dirty-worktree label."""
    if not git_status:
        return ""
    return "<dirty worktree; rerun from clean commit before launch>"


def _sha256_bytes(raw: bytes) -> str:
    """Return a SHA-256 digest for bytes."""
    return hashlib.sha256(raw).hexdigest()


def _read_source_report(source_report: Path) -> tuple[dict[str, Any], str]:
    """Read and validate one full extraction eval report."""
    raw = source_report.read_bytes()
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("extraction_report_must_be_object")
    summary = payload.get("summary")
    cases = payload.get("cases")
    if not isinstance(summary, dict):
        raise ValueError("extraction_report_missing_summary")
    if not isinstance(cases, list):
        raise ValueError("extraction_report_missing_cases")
    _validate_source_report(summary=summary, cases=cases, payload=payload)
    return payload, _sha256_bytes(raw)


def _validate_source_report(
    *,
    summary: dict[str, Any],
    cases: list[Any],
    payload: dict[str, Any],
) -> None:
    """Validate source aggregate/case consistency before sanitizing."""
    case_count = len(cases)
    for field in ("num_traces",):
        expected = _optional_int(payload.get(field))
        if expected is not None and expected != case_count:
            raise ValueError(f"extraction_report_{field}_mismatch")
    for field in ("dataset_case_count", "full_dataset_case_count"):
        expected = _optional_int(summary.get(field))
        if expected is not None and expected != case_count:
            raise ValueError(f"extraction_report_{field}_mismatch")
    source_profile_counts = summary.get("source_profile_counts")
    if isinstance(source_profile_counts, dict):
        profile_total = sum(
            int(value)
            for value in source_profile_counts.values()
            if isinstance(value, int | float)
        )
        if profile_total != case_count:
            raise ValueError("extraction_report_source_profile_counts_mismatch")
    for index, item in enumerate(cases):
        if not isinstance(item, dict):
            raise ValueError(f"extraction_report_case_{index}_must_be_object")
        if not str(item.get("name") or "").strip():
            raise ValueError(f"extraction_report_case_{index}_missing_name")
        scores = item.get("scores")
        if scores is not None and not isinstance(scores, dict):
            raise ValueError(f"extraction_report_case_{index}_scores_must_be_object")


def _optional_int(value: Any) -> int | None:
    """Return an int for present count-like values."""
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("extraction_report_count_must_be_integer") from exc


def _safe_summary(summary: dict[str, Any]) -> dict[str, Any]:
    """Return only public-safe aggregate summary fields."""
    return {key: summary[key] for key in SUMMARY_FIELDS if key in summary}


def _headline(summary: dict[str, Any]) -> dict[str, Any]:
    """Return the compact headline metric payload."""
    return {key: summary[key] for key, _label in HEADLINE_FIELDS if key in summary}


def _public_command(argv: list[str]) -> str:
    """Return the report command with private source-report paths redacted."""
    redacted: list[str] = []
    skip_next = False
    for arg in argv:
        if skip_next:
            redacted.append("<private-source-report>")
            skip_next = False
            continue
        if arg == "--source-report":
            redacted.append(arg)
            skip_next = True
            continue
        if arg.startswith("--source-report="):
            redacted.append("--source-report=<private-source-report>")
            continue
        redacted.append(arg)
    return " ".join(shlex.quote(part) for part in redacted)


def build_report(
    *,
    source_report: Path,
    source_payload: dict[str, Any],
    source_sha256: str,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Build the public sanitized extraction-quality report."""
    summary = source_payload["summary"]
    cases = source_payload["cases"]
    git_status = _git_value(["status", "--short"])
    return {
        "schema_version": 1,
        "benchmark": BENCHMARK_ID,
        "generated_at": generated_at or _utc_now(),
        "command": _public_command(sys.argv),
        "artifact_scope": "aggregate_only",
        "public_sanitized": True,
        "publication_status": "development_baseline_not_launch_grade",
        "source_artifact": {
            "label": "private first-party extraction eval artifact",
            "visibility": "private",
            "sha256": source_sha256,
        },
        "model_provider": {
            "agent_provider": source_payload.get("agent_provider"),
            "agent_model": source_payload.get("agent_model"),
            "judge_model": source_payload.get("judge_model"),
            "llm_in_loop": True,
            "semantic_judge_in_loop": True,
        },
        "dataset": {
            "cases": int(source_payload.get("num_traces") or len(cases)),
            "dataset_case_count": summary.get("dataset_case_count"),
            "full_dataset_case_count": summary.get("full_dataset_case_count"),
            "dataset_coverage_rate_pct": summary.get("dataset_coverage_rate_pct"),
            "case_failures": summary.get("case_failures"),
        },
        "methodology": {
            "task": "trace_to_context_extraction_quality",
            "framework": source_payload.get("framework"),
            "raw_trace_text_included": False,
            "extracted_record_text_included": False,
            "tool_payloads_included": False,
            "judge_detail_included": False,
            "aggregate_metrics_included": True,
            "per_case_numeric_metrics_included": False,
            "competitor_scores_available": False,
            "not_comparable_to_retrieval_only_scores": True,
        },
        "results": {
            "headline": _headline(summary),
            "summary": _safe_summary(summary),
        },
        "required_artifacts": [
            "report.json",
            "report.md",
        ],
        "limitations": [
            "This is an aggregate-only public report derived from a full LLM-backed extraction artifact.",
            "Raw traces, extracted record text, tool payloads, case identifiers, per-case metrics, and judge details are intentionally excluded.",
            "Treat this as development baseline evidence until rerun from a clean release state.",
            "These metrics measure trace-to-context extraction quality, not LongMemEval retrieval or answer-generation accuracy.",
            "Competitors have not been run on this private labeled eval, so their scores are not available.",
        ],
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "machine": platform.machine(),
            "lerim_git_commit": _git_value(["rev-parse", "HEAD"]),
            "lerim_git_dirty": bool(git_status),
            "lerim_git_status_short": _public_git_status(git_status),
        },
    }


def _format_metric(value: Any) -> str:
    """Format a metric value for Markdown."""
    if isinstance(value, int | float):
        if 0.0 <= float(value) <= 1.0:
            return f"{float(value) * 100:.2f}%"
        return f"{float(value):.2f}%"
    return str(value)


def render_markdown(report: dict[str, Any]) -> str:
    """Render the aggregate-only extraction report as Markdown."""
    headline = report["results"]["headline"]
    dataset = report["dataset"]
    source = report["source_artifact"]
    model = report["model_provider"]
    lines = [
        "# Lerim Extraction Quality Benchmark",
        "",
        f"- Generated: `{report['generated_at']}`",
        f"- Command: `{report['command']}`",
        f"- Source artifact: `{source['label']}`",
        f"- Source visibility: `{source['visibility']}`",
        f"- Source digest: `{source['sha256']}`",
        f"- Agent model: `{model['agent_provider']} / {model['agent_model']}`",
        f"- Judge model: `{model['judge_model']}`",
        f"- Dataset cases: `{dataset['cases']}`",
        f"- Aggregate-only public artifact: `{report['public_sanitized']}`",
        f"- Publication status: `{report['publication_status']}`",
        "",
        "## Headline",
        "",
        "| Metric | Result |",
        "|---|---:|",
    ]
    for key, label in HEADLINE_FIELDS:
        if key in headline:
            lines.append(f"| {label} | {_format_metric(headline[key])} |")
    lines.extend(
        [
            "",
            "## Dataset Coverage",
            "",
            f"- Cases: `{dataset['dataset_case_count']}` / `{dataset['full_dataset_case_count']}`",
            f"- Dataset coverage: `{_format_metric(dataset['dataset_coverage_rate_pct'])}`",
            f"- Case failures: `{dataset['case_failures']}`",
            "",
        ]
    )
    lines.extend(
        [
            "",
            "## Public Artifact Boundary",
            "",
        ]
    )
    for limitation in report["limitations"]:
        lines.append(f"- {limitation}")
    lines.extend(
        [
            "",
            "Do not compare these extraction metrics to LongMemEval retrieval-only metrics.",
            "Competitor scores are not available for this private labeled eval.",
            "",
        ]
    )
    return "\n".join(lines)


def write_outputs(report: dict[str, Any], output_dir: Path) -> None:
    """Write public aggregate report JSON and Markdown."""
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "report.md").write_text(render_markdown(report), encoding="utf-8")
    stale_case_metrics = output_dir / "case_metrics.jsonl"
    if stale_case_metrics.exists():
        stale_case_metrics.unlink()


def run(args: argparse.Namespace) -> Path:
    """Import one sanitized extraction-quality report."""
    source_report = args.source_report.expanduser().resolve()
    payload, digest = _read_source_report(source_report)
    report = build_report(
        source_report=source_report,
        source_payload=payload,
        source_sha256=digest,
    )
    output_dir = args.output_dir.expanduser().resolve()
    write_outputs(report, output_dir)
    return output_dir


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Import an aggregate-only public Lerim extraction-quality report.",
    )
    parser.add_argument("--source-report", type=Path, default=DEFAULT_SOURCE_REPORT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    """Run the importer from the command line."""
    output_dir = run(parse_args())
    print(f"Extraction quality report written to {output_dir}")


if __name__ == "__main__":
    main()
