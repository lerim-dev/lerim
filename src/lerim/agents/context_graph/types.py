"""Public types returned by the context-graph flow."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ContextGraphEvent(BaseModel):
    """One structured event emitted by the context-graph agent."""

    action: str
    ok: bool = True
    content: str = ""
    args: dict[str, Any] = Field(default_factory=dict)
    done: bool = False
    completion_summary: str = ""


class ContextGraphResult(BaseModel):
    """Structured output for the context-graph flow."""

    completion_summary: str = Field(description="Short plain-text completion summary")
    nodes_written: int = 0
    edges_written: int = 0
    semantic_clusters: int = 0


class ContextGraphRunDetails(BaseModel):
    """Structured trace for one context-graph run."""

    events: list[ContextGraphEvent] = Field(default_factory=list)
    llm_calls: int = 0
    done: bool = False
    context_db_path: str
    project_id: str
    session_id: str
    model_name: str
    active_record_count: int = 0
    semantic_cluster_count: int = 0
    candidate_pair_count: int = 0
    proposed_link_count: int = 0
    written_node_count: int = 0
    written_edge_count: int = 0
