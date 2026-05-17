"""LangGraph state for BAML context graph linking."""

from __future__ import annotations

import operator
from typing import Annotated, Any
from typing_extensions import TypedDict


class ContextGraphGraphState(TypedDict, total=False):
    """State for the BAML/LangGraph context-graph pipeline."""

    observations: Annotated[list[dict[str, Any]], operator.add]
    llm_calls: int
    records: list[dict[str, Any]]
    records_by_id: dict[str, dict[str, Any]]
    semantic_clusters: list[dict[str, Any]]
    candidate_pairs: list[dict[str, Any]]
    existing_edges: list[dict[str, Any]]
    proposed_links: Annotated[list[dict[str, Any]], operator.add]
    reviewed_links: list[dict[str, Any]]
    write_summary: dict[str, Any]
    done: bool
    completion_summary: str
