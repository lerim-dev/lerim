"""Unit tests for context-budget benchmark helpers."""

from __future__ import annotations

from benchmarks.lerim_evidence.context_budget import context_reduction_ratio, summarize


def test_context_reduction_ratio() -> None:
    """Context reduction uses real counts and clamps impossible negative values."""
    assert context_reduction_ratio(full_tokens=100, selected_tokens=25) == 0.75
    assert context_reduction_ratio(full_tokens=100, selected_tokens=125) == 0.0
    assert context_reduction_ratio(full_tokens=0, selected_tokens=10) == 0.0


def test_summarize_aggregates_top_k_context_reduction() -> None:
    """Summary keeps top-K context reduction and recall side by side."""
    rows = [
        {
            "question_type": "single-session-user",
            "full_haystack_tokens": 100,
            "selected_by_k": {
                "top_1": {"selected_tokens": 10, "tokens_reduced": 90, "reduction_ratio": 0.9, "recall_any": 0.0},
                "top_3": {"selected_tokens": 20, "tokens_reduced": 80, "reduction_ratio": 0.8, "recall_any": 1.0},
                "top_5": {"selected_tokens": 30, "tokens_reduced": 70, "reduction_ratio": 0.7, "recall_any": 1.0},
                "top_10": {"selected_tokens": 40, "tokens_reduced": 60, "reduction_ratio": 0.6, "recall_any": 1.0},
                "top_20": {"selected_tokens": 50, "tokens_reduced": 50, "reduction_ratio": 0.5, "recall_any": 1.0},
            },
        },
        {
            "question_type": "single-session-user",
            "full_haystack_tokens": 200,
            "selected_by_k": {
                "top_1": {"selected_tokens": 20, "tokens_reduced": 180, "reduction_ratio": 0.9, "recall_any": 1.0},
                "top_3": {"selected_tokens": 40, "tokens_reduced": 160, "reduction_ratio": 0.8, "recall_any": 1.0},
                "top_5": {"selected_tokens": 60, "tokens_reduced": 140, "reduction_ratio": 0.7, "recall_any": 1.0},
                "top_10": {"selected_tokens": 80, "tokens_reduced": 120, "reduction_ratio": 0.6, "recall_any": 1.0},
                "top_20": {"selected_tokens": 100, "tokens_reduced": 100, "reduction_ratio": 0.5, "recall_any": 1.0},
            },
        },
    ]
    report = summarize(rows)
    assert report["headline"]["avg_full_haystack_tokens"] == 150
    assert report["headline"]["top_10"]["avg_selected_tokens"] == 60
    assert report["headline"]["top_10"]["avg_reduction_ratio"] == 0.6
    assert report["headline"]["top_1"]["recall_any"] == 0.5
