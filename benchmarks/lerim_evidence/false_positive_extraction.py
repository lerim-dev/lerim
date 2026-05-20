"""Import an aggregate false-positive extraction diagnostic.

The full extraction eval already contains labeled negative/noise cases. This
module derives aggregate scores from those cases only, while excluding trace
text, case identifiers, extracted record bodies, tool payloads, judge reasoning,
and forbidden concept text.
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


BENCHMARK_ID = "lerim_false_positive_extraction_minimax_m27_negative_cases"
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
    / "false-positive-extraction-minimax-m27-negative-cases"
)

HEADLINE_FIELDS: tuple[tuple[str, str], ...] = (
    ("negative_case_count", "Negative cases"),
    ("no_durable_case_count", "No-durable cases"),
    ("false_positive_case_count", "False-positive cases"),
    ("negative_precision_rate_pct", "Negative precision"),
    ("false_positive_case_rate_pct", "False-positive case rate"),
    ("total_durable_records_on_negative_cases", "Durable records on negative cases"),
    ("forbidden_concept_score_avg", "Forbidden-concept score average"),
    ("signal_filtering_score_avg", "Signal-filtering score average"),
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
        raise ValueError("false_positive_source_report_must_be_object")
    summary = payload.get("summary")
    cases = payload.get("cases")
    if not isinstance(summary, dict):
        raise ValueError("false_positive_source_report_missing_summary")
    if not isinstance(cases, list):
        raise ValueError("false_positive_source_report_missing_cases")
    _validate_source_report(payload=payload, summary=summary, cases=cases)
    return payload, _sha256_bytes(raw)


def _validate_source_report(
    *,
    payload: dict[str, Any],
    summary: dict[str, Any],
    cases: list[Any],
) -> None:
    """Validate source aggregate/case consistency before deriving metrics."""
    case_count = len(cases)
    num_traces = _optional_int(payload.get("num_traces"))
    if num_traces is not None and num_traces != case_count:
        raise ValueError("false_positive_source_num_traces_mismatch")
    for field in ("dataset_case_count", "full_dataset_case_count"):
        expected = _optional_int(summary.get(field))
        if expected is not None and expected != case_count:
            raise ValueError(f"false_positive_source_{field}_mismatch")
    for index, item in enumerate(cases):
        if not isinstance(item, dict):
            raise ValueError(f"false_positive_source_case_{index}_must_be_object")
        if not str(item.get("name") or "").strip():
            raise ValueError(f"false_positive_source_case_{index}_missing_name")
        scores = item.get("scores")
        if scores is not None and not isinstance(scores, dict):
            raise ValueError(f"false_positive_source_case_{index}_scores_must_be_object")


def _optional_int(value: Any) -> int | None:
    """Return an int for present count-like values."""
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("false_positive_source_count_must_be_integer") from exc


def _safe_float(value: Any) -> float | None:
    """Return a float when the value is numeric."""
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, int | float):
        return float(value)
    return None


def _mean(values: list[float]) -> float | None:
    """Return a rounded mean for metric values."""
    if not values:
        return None
    return round(sum(values) / len(values), 4)


def _negative_cases(cases: list[Any]) -> list[dict[str, Any]]:
    """Return labeled negative cases from the full extraction source."""
    rows = [case for case in cases if isinstance(case, dict) and case.get("category") == "negative"]
    if not rows:
        raise ValueError("false_positive_source_has_no_negative_cases")
    return rows


def _must_extract_count(case: dict[str, Any], key: str) -> int:
    """Return a public-safe count from case assertions."""
    assertions = case.get("assertions")
    if not isinstance(assertions, dict):
        return 0
    items = assertions.get(key)
    if not isinstance(items, list):
        return 0
    return len(items)


def _numeric_scores(case: dict[str, Any]) -> dict[str, float]:
    """Return numeric public-safe scores for a negative case."""
    scores = case.get("scores")
    if not isinstance(scores, dict):
        return {}
    allowed = {
        "negative_precision",
        "forbidden_concept_rate",
        "signal_filtering",
        "quality_gate",
        "hard_gate_pass",
        "task_completion",
        "tool_call_errors",
    }
    numeric: dict[str, float] = {}
    for key, value in sorted(scores.items()):
        if key not in allowed:
            continue
        number = _safe_float(value)
        if number is not None:
            numeric[key] = number
    return numeric


def _case_metrics(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return public-safe per-negative-case metadata and numeric scores."""
    rows: list[dict[str, Any]] = []
    for case in cases:
        durable_record_count = int(case.get("durable_record_count") or 0)
        rows.append(
            {
                "name": str(case.get("name") or ""),
                "category": "negative",
                "source_profile": str(case.get("source_profile") or ""),
                "scope_type": str(case.get("scope_type") or ""),
                "record_count": int(case.get("record_count") or 0),
                "episode_count": int(case.get("episode_count") or 0),
                "durable_record_count": durable_record_count,
                "llm_calls": int(case.get("llm_calls") or 0),
                "tool_call_errors": int(case.get("tool_call_errors") or 0),
                "failure": str(case.get("failure") or ""),
                "assertion_counts": {
                    "must_extract": _must_extract_count(case, "must_extract"),
                    "must_not_extract": _must_extract_count(case, "must_not_extract"),
                    "expected_episode_count": _assertion_count(case, "expected_episode_count"),
                    "min_durable_records": _assertion_count(case, "min_durable_records"),
                    "max_durable_records": _assertion_count(case, "max_durable_records"),
                },
                "scores": _numeric_scores(case),
                "created_durable_records": durable_record_count > 0,
            }
        )
    return rows


def _assertion_count(case: dict[str, Any], key: str) -> int | None:
    """Return a public-safe numeric assertion value."""
    assertions = case.get("assertions")
    if not isinstance(assertions, dict):
        return None
    value = assertions.get(key)
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _source_profile_counts(cases: list[dict[str, Any]]) -> dict[str, int]:
    """Count source profiles among negative cases."""
    counts: dict[str, int] = {}
    for case in cases:
        profile = str(case.get("source_profile") or "unknown")
        counts[profile] = counts.get(profile, 0) + 1
    return dict(sorted(counts.items()))


def _summary(case_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute false-positive extraction metrics from sanitized case rows."""
    negative_case_count = len(case_rows)
    no_durable_case_count = sum(
        1 for row in case_rows if int(row["durable_record_count"]) == 0
    )
    false_positive_case_count = negative_case_count - no_durable_case_count
    total_durable = sum(int(row["durable_record_count"]) for row in case_rows)
    total_records = sum(int(row["record_count"]) for row in case_rows)
    total_llm_calls = sum(int(row["llm_calls"]) for row in case_rows)
    score_values: dict[str, list[float]] = {
        "negative_precision": [],
        "forbidden_concept_rate": [],
        "signal_filtering": [],
        "quality_gate": [],
        "hard_gate_pass": [],
    }
    for row in case_rows:
        scores = row.get("scores")
        if not isinstance(scores, dict):
            continue
        for key in score_values:
            value = _safe_float(scores.get(key))
            if value is not None:
                score_values[key].append(value)

    negative_precision_avg = _mean(score_values["negative_precision"])
    negative_precision_rate_pct = (
        round(float(negative_precision_avg) * 100.0, 2)
        if negative_precision_avg is not None
        else round((no_durable_case_count / negative_case_count) * 100.0, 2)
    )
    false_positive_case_rate_pct = round(
        (false_positive_case_count / negative_case_count) * 100.0,
        2,
    )
    return {
        "negative_case_count": negative_case_count,
        "no_durable_case_count": no_durable_case_count,
        "false_positive_case_count": false_positive_case_count,
        "negative_precision_rate_pct": negative_precision_rate_pct,
        "false_positive_case_rate_pct": false_positive_case_rate_pct,
        "total_records_on_negative_cases": total_records,
        "total_durable_records_on_negative_cases": total_durable,
        "total_llm_calls_on_negative_cases": total_llm_calls,
        "forbidden_concept_score_avg": _mean(score_values["forbidden_concept_rate"]),
        "signal_filtering_score_avg": _mean(score_values["signal_filtering"]),
        "quality_gate_score_avg": _mean(score_values["quality_gate"]),
        "hard_gate_score_avg": _mean(score_values["hard_gate_pass"]),
    }


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
    """Build the aggregate-only false-positive extraction report."""
    cases = source_payload["cases"]
    negative_cases = _negative_cases(cases)
    case_rows = _case_metrics(negative_cases)
    summary = _summary(case_rows)
    git_status = _git_value(["status", "--short"])
    return {
        "schema_version": 1,
        "benchmark": BENCHMARK_ID,
        "generated_at": generated_at or _utc_now(),
        "command": _public_command(sys.argv),
        "artifact_scope": "aggregate_only_negative_slice",
        "public_sanitized": True,
        "publication_status": "diagnostic_development_guardrail_not_market_comparison",
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
            "source_total_cases": len(cases),
            "negative_cases": len(negative_cases),
            "selection_rule": "case.category == 'negative'",
        },
        "methodology": {
            "task": "false_positive_extraction_on_negative_source_sessions",
            "raw_trace_text_included": False,
            "extracted_record_text_included": False,
            "tool_payloads_included": False,
            "judge_detail_included": False,
            "forbidden_concept_text_included": False,
            "aggregate_metrics_included": True,
            "per_case_numeric_metrics_included": False,
            "competitor_scores_available": False,
            "not_comparable_to_retrieval_only_scores": True,
        },
        "results": {
            "headline": summary,
            "summary": summary,
        },
        "required_artifacts": [
            "report.json",
            "report.md",
        ],
        "limitations": [
            "This diagnostic is derived from the negative/noise cases in the 47-case LLM-backed extraction artifact.",
            "It measures whether Lerim avoids durable records when labeled source sessions have no durable signal.",
            "Raw traces, case identifiers, extracted record text, tool payloads, forbidden concept text, per-case metrics, and judge details are intentionally excluded.",
            "Treat this as internal development evidence until rerun from a clean release state.",
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
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if 0.0 <= value <= 1.0:
            return f"{value * 100:.2f}%"
        return f"{value:.2f}%"
    return str(value)


def render_markdown(report: dict[str, Any]) -> str:
    """Render the aggregate-only false-positive extraction report as Markdown."""
    headline = report["results"]["headline"]
    dataset = report["dataset"]
    source = report["source_artifact"]
    model = report["model_provider"]
    lines = [
        "# Lerim False-Positive Extraction Diagnostic",
        "",
        f"- Generated: `{report['generated_at']}`",
        f"- Command: `{report['command']}`",
        f"- Source artifact: `{source['label']}`",
        f"- Source visibility: `{source['visibility']}`",
        f"- Source digest: `{source['sha256']}`",
        f"- Agent model: `{model['agent_provider']} / {model['agent_model']}`",
        f"- Judge model: `{model['judge_model']}`",
        f"- Source cases: `{dataset['source_total_cases']}`",
        f"- Negative cases: `{dataset['negative_cases']}`",
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
            "## Dataset Slice",
            "",
            f"- Selection rule: `{dataset['selection_rule']}`",
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
            "Do not compare this diagnostic to LongMemEval retrieval-only metrics or market rows.",
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
    """Import one aggregate-only false-positive extraction report."""
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
        description="Import a sanitized Lerim false-positive extraction report.",
    )
    parser.add_argument("--source-report", type=Path, default=DEFAULT_SOURCE_REPORT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    """Run the importer from the command line."""
    output_dir = run(parse_args())
    print(f"False-positive extraction report written to {output_dir}")


if __name__ == "__main__":
    main()
