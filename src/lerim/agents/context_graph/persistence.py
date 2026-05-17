"""Persistence helpers for the derived context graph."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lerim.agents.context_graph.clustering import build_cluster_assignments
from lerim.context import ContextStore, ProjectIdentity, scope_from_project


@dataclass
class ContextGraphWriteSummary:
    """Summary of one persisted context-graph refresh."""

    nodes_written: int = 0
    edges_written: int = 0
    semantic_clusters: int = 0
    observations: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        """Return a compact JSON-serializable summary."""
        return {
            "nodes_written": self.nodes_written,
            "edges_written": self.edges_written,
            "semantic_clusters": self.semantic_clusters,
        }


def replace_context_graph(
    *,
    context_db_path: Path,
    project_identity: ProjectIdentity,
    session_id: str,
    records: list[dict[str, Any]],
    semantic_clusters: list[dict[str, Any]],
    candidate_pairs: list[dict[str, Any]],
    links: list[dict[str, Any]],
) -> ContextGraphWriteSummary:
    """Refresh the graph projection for the reviewed record window."""
    store = ContextStore(context_db_path)
    store.initialize()
    store.register_project(project_identity)
    scope = scope_from_project(project_identity)
    refresh_record_ids = {
        str(record.get("record_id") or "").strip()
        for record in records
        if str(record.get("record_id") or "").strip()
    }
    cluster_assignments = build_cluster_assignments(
        records=records,
        semantic_clusters=semantic_clusters,
    )
    semantic_labels = {
        value["semantic_cluster"]
        for value in cluster_assignments.values()
        if value["semantic_cluster"] != "semantic_unclustered"
    }
    summary = ContextGraphWriteSummary(
        semantic_clusters=len(semantic_labels),
    )

    with store.connect() as conn:
        now = _utc_now_from_store()
        _archive_graph_rows_without_active_records(
            conn,
            project_id=project_identity.project_id,
            updated_at=now,
        )
        if refresh_record_ids:
            placeholders = ", ".join("?" for _ in refresh_record_ids)
            ordered_record_ids = sorted(refresh_record_ids)
            conn.execute(
                f"""
                UPDATE context_nodes
                SET status = 'archived', updated_at = ?
                WHERE project_id = ?
                  AND status != 'archived'
                  AND node_id IN ({placeholders})
                """,
                (now, project_identity.project_id, *ordered_record_ids),
            )
        _archive_removed_candidate_edges(
            conn,
            project_id=project_identity.project_id,
            candidate_pairs=candidate_pairs,
            links=links,
            updated_at=now,
        )

        for record in records:
            record_id = str(record.get("record_id") or "").strip()
            if not record_id:
                continue
            clusters = cluster_assignments.get(record_id, {})
            conn.execute(
                """
                INSERT INTO context_nodes(
                    node_id, project_id, scope_type, scope_id, scope_label,
                    node_type, label, summary, status, semantic_cluster,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(node_id) DO UPDATE SET
                    project_id=excluded.project_id,
                    scope_type=excluded.scope_type,
                    scope_id=excluded.scope_id,
                    scope_label=excluded.scope_label,
                    node_type=excluded.node_type,
                    label=excluded.label,
                    summary=excluded.summary,
                    status=excluded.status,
                    semantic_cluster=excluded.semantic_cluster,
                    updated_at=excluded.updated_at
                """,
                (
                    record_id,
                    project_identity.project_id,
                    scope.scope_type,
                    scope.scope_id,
                    scope.label,
                    "context_record",
                    str(record.get("title") or record_id).strip()[:240],
                    str(record.get("body") or "").strip()[:1200] or None,
                    "active",
                    clusters.get("semantic_cluster", "semantic_unclustered"),
                    now,
                    now,
                ),
            )
            summary.nodes_written += 1

        for link in links:
            source_id = str(link.get("source_record_id") or "").strip()
            target_id = str(link.get("target_record_id") or "").strip()
            relation_kind = str(link.get("relation_kind") or "").strip().lower()
            if not source_id or not target_id or not relation_kind:
                continue
            edge_id = _edge_id(
                project_id=project_identity.project_id,
                source_id=source_id,
                target_id=target_id,
                relation_kind=relation_kind,
            )
            evidence = _json_list(link.get("evidence_record_ids") or [source_id, target_id])
            conn.execute(
                """
                INSERT INTO context_edges(
                    edge_id, project_id, scope_type, scope_id, scope_label,
                    source_node_id, target_node_id, relation_kind, label,
                    rationale, evidence_record_ids, confidence, status,
                    created_at, updated_at, created_by_session_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(project_id, source_node_id, target_node_id, relation_kind) DO UPDATE SET
                    scope_type=excluded.scope_type,
                    scope_id=excluded.scope_id,
                    scope_label=excluded.scope_label,
                    label=excluded.label,
                    rationale=excluded.rationale,
                    evidence_record_ids=excluded.evidence_record_ids,
                    confidence=excluded.confidence,
                    status=excluded.status,
                    updated_at=excluded.updated_at,
                    created_by_session_id=excluded.created_by_session_id
                """,
                (
                    edge_id,
                    project_identity.project_id,
                    scope.scope_type,
                    scope.scope_id,
                    scope.label,
                    source_id,
                    target_id,
                    relation_kind,
                    str(link.get("label") or relation_kind).strip()[:180],
                    str(link.get("rationale") or "").strip()[:1200] or None,
                    json.dumps(evidence, ensure_ascii=True),
                    max(0.0, min(1.0, float(link.get("confidence") or 0.5))),
                    "active",
                    now,
                    now,
                    session_id,
                ),
            )
            summary.edges_written += 1

    summary.observations.append(
        {
            "action": "persist_context_graph",
            "ok": True,
            "content": (
                f"nodes={summary.nodes_written} edges={summary.edges_written} "
                f"semantic_clusters={summary.semantic_clusters}"
            ),
            "args": summary.as_dict(),
        }
    )
    return summary


def _archive_graph_rows_without_active_records(
    conn,
    *,
    project_id: str,
    updated_at: str,
) -> None:
    """Archive graph rows whose backing context records are no longer active."""
    active_record_sql = """
        SELECT record_id
        FROM records
        WHERE project_id = ?
          AND status = 'active'
          AND kind != 'episode'
    """
    conn.execute(
        f"""
        UPDATE context_edges
        SET status = 'archived', updated_at = ?
        WHERE project_id = ?
          AND status != 'archived'
          AND (
            source_node_id NOT IN ({active_record_sql})
            OR target_node_id NOT IN ({active_record_sql})
          )
        """,
        (updated_at, project_id, project_id, project_id),
    )
    conn.execute(
        f"""
        UPDATE context_nodes
        SET status = 'archived', updated_at = ?
        WHERE project_id = ?
          AND status != 'archived'
          AND node_id NOT IN ({active_record_sql})
        """,
        (updated_at, project_id, project_id),
    )


def _archive_removed_candidate_edges(
    conn,
    *,
    project_id: str,
    candidate_pairs: list[dict[str, Any]],
    links: list[dict[str, Any]],
    updated_at: str,
) -> None:
    """Archive reviewed candidate-space edges that were not kept by the model."""
    kept: dict[tuple[str, str], set[str]] = {}
    for link in links:
        source_id = str(link.get("source_record_id") or "").strip()
        target_id = str(link.get("target_record_id") or "").strip()
        relation_kind = str(link.get("relation_kind") or "").strip().lower()
        if not source_id or not target_id or not relation_kind:
            continue
        kept.setdefault((source_id, target_id), set()).add(relation_kind)

    for pair in candidate_pairs:
        source_id = str(pair.get("source_record_id") or "").strip()
        target_id = str(pair.get("target_record_id") or "").strip()
        if not source_id or not target_id or source_id == target_id:
            continue
        for edge_source, edge_target in ((source_id, target_id), (target_id, source_id)):
            kept_kinds = kept.get((edge_source, edge_target), set())
            if kept_kinds:
                placeholders = ", ".join("?" for _ in kept_kinds)
                conn.execute(
                    f"""
                    UPDATE context_edges
                    SET status = 'archived', updated_at = ?
                    WHERE project_id = ?
                      AND source_node_id = ?
                      AND target_node_id = ?
                      AND status != 'archived'
                      AND relation_kind NOT IN ({placeholders})
                    """,
                    (updated_at, project_id, edge_source, edge_target, *sorted(kept_kinds)),
                )
            else:
                conn.execute(
                    """
                    UPDATE context_edges
                    SET status = 'archived', updated_at = ?
                    WHERE project_id = ?
                      AND source_node_id = ?
                      AND target_node_id = ?
                      AND status != 'archived'
                    """,
                    (updated_at, project_id, edge_source, edge_target),
                )


def _edge_id(
    *,
    project_id: str,
    source_id: str,
    target_id: str,
    relation_kind: str,
) -> str:
    """Return a deterministic graph edge identifier."""
    payload = f"{project_id}|{source_id}|{target_id}|{relation_kind}".encode("utf-8")
    return f"edge_{hashlib.sha256(payload).hexdigest()[:20]}"


def _json_list(value: Any) -> list[str]:
    """Normalize a candidate evidence list to non-empty strings."""
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        text = str(item or "").strip()
        if text and text not in result:
            result.append(text)
    return result


def _utc_now_from_store() -> str:
    """Return current UTC timestamp for graph projection rows."""
    return datetime.now(timezone.utc).isoformat()
