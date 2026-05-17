"""Semantic cluster assignment helpers for persisted context graph nodes."""

from __future__ import annotations

from typing import Any


def build_cluster_assignments(
    *,
    records: list[dict[str, Any]],
    semantic_clusters: list[dict[str, Any]],
) -> dict[str, dict[str, str]]:
    """Return persisted semantic cluster labels by record."""
    record_ids = [str(record.get("record_id") or "") for record in records if str(record.get("record_id") or "")]
    semantic = _semantic_assignments(record_ids, semantic_clusters)
    return {
        record_id: {
            "semantic_cluster": semantic.get(record_id, "semantic_unclustered"),
        }
        for record_id in record_ids
    }


def _semantic_assignments(
    record_ids: list[str],
    semantic_clusters: list[dict[str, Any]],
) -> dict[str, str]:
    """Assign semantic-neighbor cluster labels."""
    assignments = {record_id: "semantic_unclustered" for record_id in record_ids}
    for index, cluster in enumerate(semantic_clusters, start=1):
        cluster_id = str(cluster.get("cluster_id") or f"semantic_{index}")
        for record_id in cluster.get("record_ids") or []:
            text_id = str(record_id or "")
            if text_id in assignments:
                assignments[text_id] = cluster_id
    return assignments
