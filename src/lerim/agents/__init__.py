"""Agent modules for trace-ingestion, context graph, curation, and answer flows."""

from __future__ import annotations

from typing import Any

__all__ = ["run_context_graph", "run_context_curator", "run_context_answerer"]


def __getattr__(name: str) -> Any:
	"""Lazy-load agent exports to avoid circular import cycles."""
	if name == "run_context_curator":
		from lerim.agents.context_curator import run_context_curator
		return run_context_curator
	if name == "run_context_graph":
		from lerim.agents.context_graph import run_context_graph
		return run_context_graph
	if name == "run_context_answerer":
		from lerim.agents.context_answerer import run_context_answerer
		return run_context_answerer
	raise AttributeError(name)
