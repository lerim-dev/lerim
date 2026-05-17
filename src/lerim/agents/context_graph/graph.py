"""LangGraph context-graph linking pipeline backed by BAML."""

from __future__ import annotations

from typing import Any, Callable

from langgraph.graph import END, START, StateGraph

from lerim.agents.baml_runtime import build_baml_client_for_role
from lerim.agents.context_graph.inventory import (
    build_semantic_candidates,
    format_edges_json,
    format_pairs_json,
    format_records_json,
    load_existing_edges,
    load_graph_records,
)
from lerim.agents.context_graph.persistence import replace_context_graph
from lerim.agents.context_graph.state import ContextGraphGraphState
from lerim.config.settings import Config
from lerim.context import ProjectIdentity

MAX_BAML_MODEL_RETRIES = 3
BAML_RECOVERABLE_ERROR_NAMES = {
    "BamlClientFinishReasonError",
    "BamlClientHttpError",
    "BamlTimeoutError",
    "BamlValidationError",
}
SUPPORTED_RELATION_KINDS = {
    "supports",
    "refines",
    "depends_on",
    "contradicts",
    "same_topic",
    "evidence_for",
    "supersedes",
    "related",
}


def run_context_graph_graph(
    *,
    context_db_path,
    project_identity: ProjectIdentity,
    session_id: str,
    config: Config,
    provider: str | None = None,
    model_name: str | None = None,
    api_base_url: str | None = None,
    api_key: str | None = None,
    temperature: float | None = None,
    max_llm_calls: int | None = None,
    progress: bool = False,
) -> dict[str, Any]:
    """Run the BAML context-graph pipeline and return its final state."""
    graph = build_context_graph_graph(
        context_db_path=context_db_path,
        project_identity=project_identity,
        session_id=session_id,
        config=config,
        provider=provider,
        model_name=model_name,
        api_base_url=api_base_url,
        api_key=api_key,
        temperature=temperature,
        max_llm_calls=max_llm_calls or 20,
        progress=progress,
    )
    return graph.invoke(
        {
            "observations": [],
            "llm_calls": 0,
            "records": [],
            "records_by_id": {},
            "semantic_clusters": [],
            "candidate_pairs": [],
            "existing_edges": [],
            "proposed_links": [],
            "reviewed_links": [],
            "write_summary": {},
            "done": False,
            "completion_summary": "",
        }
    )


def build_context_graph_graph(
    *,
    context_db_path,
    project_identity: ProjectIdentity,
    session_id: str,
    config: Config,
    provider: str | None,
    model_name: str | None,
    api_base_url: str | None,
    api_key: str | None,
    temperature: float | None,
    max_llm_calls: int,
    progress: bool = False,
):
    """Compile context graph inventory, linking, review, and persistence phases."""
    baml_runtime: Any | None = None
    run_instruction = _run_instruction()

    def get_baml_runtime() -> Any:
        """Build the BAML client only when an LLM call is actually needed."""
        nonlocal baml_runtime
        if baml_runtime is None:
            baml_runtime = build_baml_client_for_role(
                config=config,
                provider=provider,
                model_name=model_name,
                api_base_url=api_base_url,
                api_key=api_key,
                temperature=temperature,
            )
        return baml_runtime

    def load_inventory(state: ContextGraphGraphState) -> dict[str, Any]:
        """Load active durable records and existing graph edges."""
        del state
        records = load_graph_records(
            context_db_path=context_db_path,
            project_identity=project_identity,
        )
        existing_edges = load_existing_edges(
            context_db_path=context_db_path,
            project_identity=project_identity,
        )
        if progress:
            print(f"  context-graph inventory active_records={len(records)}", flush=True)
        return {
            "records": records,
            "records_by_id": {str(record["record_id"]): record for record in records},
            "existing_edges": existing_edges,
            "observations": [
                _observation(
                    "load_inventory",
                    True,
                    f"active_records={len(records)} existing_edges={len(existing_edges)}",
                    {
                        "record_count": len(records),
                        "existing_edge_count": len(existing_edges),
                    },
                )
            ],
        }

    def build_candidates(state: ContextGraphGraphState) -> dict[str, Any]:
        """Build semantic clusters and candidate link pairs."""
        records = state.get("records") or []
        semantic_clusters, candidate_pairs = build_semantic_candidates(
            context_db_path=context_db_path,
            project_identity=project_identity,
            records=records,
        )
        if progress:
            print(
                f"  context-graph semantic_clusters={len(semantic_clusters)} pairs={len(candidate_pairs)}",
                flush=True,
            )
        return {
            "semantic_clusters": semantic_clusters,
            "candidate_pairs": candidate_pairs,
            "observations": [
                _observation(
                    "build_semantic_candidates",
                    True,
                    f"semantic_clusters={len(semantic_clusters)} candidate_pairs={len(candidate_pairs)}",
                    {
                        "semantic_cluster_count": len(semantic_clusters),
                        "candidate_pair_count": len(candidate_pairs),
                    },
                )
            ],
        }

    def link_records(state: ContextGraphGraphState) -> dict[str, Any]:
        """Ask BAML to link semantic candidate pairs."""
        llm_calls = int(state.get("llm_calls") or 0)
        observations: list[dict[str, Any]] = []
        links: list[dict[str, Any]] = []
        records_by_id = state.get("records_by_id") or {}
        existing_edges = state.get("existing_edges") or []
        for cluster in state.get("semantic_clusters") or []:
            pairs = cluster.get("candidate_pairs") or []
            if not pairs:
                continue
            if llm_calls >= max_llm_calls:
                raise RuntimeError(f"BAML context graph exceeded max_llm_calls={max_llm_calls}.")
            if progress:
                print(f"  context-graph link cluster {cluster.get('cluster_id')}", flush=True)
            allowed_pairs = _allowed_pair_set(pairs)
            result, retry_observations, attempts = _call_baml_with_retries(
                lambda instruction, cluster=cluster, pairs=pairs: get_baml_runtime().LinkContextRecords(
                    run_instruction=instruction,
                    cluster_id=str(cluster.get("cluster_id") or ""),
                    records_json=format_records_json(cluster.get("records") or []),
                    candidate_pairs_json=format_pairs_json(pairs),
                    existing_edges_json=format_edges_json(existing_edges),
                ),
                stage="link_records",
                progress=progress,
                run_instruction=run_instruction,
                validate_result=lambda result, records_by_id=records_by_id: _validate_links_for_records(
                    result,
                    records_by_id=records_by_id,
                    allowed_pairs=allowed_pairs,
                ),
            )
            llm_calls += attempts
            cluster_links = _extract_links(result)
            links.extend(cluster_links)
            observations.extend(retry_observations)
            observations.append(
                _observation(
                    "link_records",
                    True,
                    f"cluster={cluster.get('cluster_id')} proposed_links={len(cluster_links)}",
                    {
                        "cluster_id": cluster.get("cluster_id"),
                        "proposed_link_count": len(cluster_links),
                    },
                )
            )
        if not links:
            observations.append(
                _observation(
                    "link_records",
                    True,
                    "No graph links proposed.",
                    {"proposed_link_count": 0},
                )
            )
        return {"llm_calls": llm_calls, "proposed_links": links, "observations": observations}

    def review_links(state: ContextGraphGraphState) -> dict[str, Any]:
        """Review proposed links before persistence."""
        proposed_links = _dedupe_links(state.get("proposed_links") or [])
        if not proposed_links:
            return {
                "reviewed_links": [],
                "observations": [
                    _observation(
                        "review_links",
                        True,
                        "No graph links to review.",
                        {"reviewed_link_count": 0},
                    )
                ],
            }
        llm_calls = int(state.get("llm_calls") or 0)
        if llm_calls >= max_llm_calls:
            raise RuntimeError(f"BAML context graph exceeded max_llm_calls={max_llm_calls}.")
        allowed_pairs = _allowed_pair_set(state.get("candidate_pairs") or [])
        result, retry_observations, attempts = _call_baml_with_retries(
            lambda instruction: get_baml_runtime().ReviewContextGraphLinks(
                run_instruction=instruction,
                records_json=format_records_json(state.get("records") or []),
                proposed_links_json=format_edges_json(proposed_links),
            ),
            stage="review_links",
            progress=progress,
            run_instruction=run_instruction,
            validate_result=lambda result: _validate_links_for_records(
                result,
                records_by_id=state.get("records_by_id") or {},
                allowed_pairs=allowed_pairs,
            ),
        )
        reviewed_links = _dedupe_links(_extract_links(result))
        if progress:
            print(f"  context-graph reviewed_links={len(reviewed_links)}", flush=True)
        return {
            "llm_calls": llm_calls + attempts,
            "reviewed_links": reviewed_links,
            "observations": [
                *retry_observations,
                _observation(
                    "review_links",
                    True,
                    f"reviewed_links={len(reviewed_links)}",
                    {"reviewed_link_count": len(reviewed_links)},
                ),
            ],
        }

    def persist_graph(state: ContextGraphGraphState) -> dict[str, Any]:
        """Persist reviewed graph nodes, links, and cluster assignments."""
        summary = replace_context_graph(
            context_db_path=context_db_path,
            project_identity=project_identity,
            session_id=session_id,
            records=state.get("records") or [],
            semantic_clusters=state.get("semantic_clusters") or [],
            candidate_pairs=state.get("candidate_pairs") or [],
            links=state.get("reviewed_links") or [],
        )
        completion_summary = (
            f"Context graph refreshed with {summary.nodes_written} node(s), "
            f"{summary.edges_written} edge(s), and {summary.semantic_clusters} semantic cluster(s)."
        )
        final = _observation(
            "final_result",
            True,
            completion_summary,
            summary.as_dict(),
        )
        final["done"] = True
        final["completion_summary"] = completion_summary
        if progress:
            print(f"  context-graph persist edges={summary.edges_written}", flush=True)
        return {
            "observations": [*summary.observations, final],
            "write_summary": summary.as_dict(),
            "done": True,
            "completion_summary": completion_summary,
        }

    graph = StateGraph(ContextGraphGraphState)
    graph.add_node("load_inventory", load_inventory)
    graph.add_node("build_candidates", build_candidates)
    graph.add_node("link_records", link_records)
    graph.add_node("review_links", review_links)
    graph.add_node("persist_graph", persist_graph)
    graph.add_edge(START, "load_inventory")
    graph.add_edge("load_inventory", "build_candidates")
    graph.add_edge("build_candidates", "link_records")
    graph.add_edge("link_records", "review_links")
    graph.add_edge("review_links", "persist_graph")
    graph.add_edge("persist_graph", END)
    return graph.compile()


def _run_instruction() -> str:
    """Return context-graph task framing for BAML calls."""
    return (
        "Build a sparse, evidence-backed context graph from curated records. "
        "Prefer a few durable relationships that help future agents navigate context. "
        "Do not link merely because two records are broadly adjacent."
    )


def _call_baml_with_retries(
    call: Callable[[str], Any],
    *,
    stage: str,
    progress: bool,
    run_instruction: str,
    validate_result: Callable[[Any], str | None] | None = None,
) -> tuple[Any, list[dict[str, Any]], int]:
    """Run one BAML call with graph-visible recoverable retries."""
    observations: list[dict[str, Any]] = []
    attempts = 0
    validation_feedback = ""
    while True:
        attempts += 1
        try:
            result = call(_instruction_with_validation_feedback(run_instruction, validation_feedback))
        except Exception as exc:
            if not _is_recoverable_baml_error(exc) or attempts > MAX_BAML_MODEL_RETRIES:
                raise
            if progress:
                print(f"  context-graph retry {stage} attempt={attempts}", flush=True)
            observations.append(
                _observation(
                    "model_retry",
                    False,
                    _model_retry_observation(exc),
                    {"stage": stage, "attempt": attempts},
                )
            )
            continue
        if validate_result is None:
            return result, observations, attempts
        validation_error = validate_result(result)
        if not validation_error:
            return result, observations, attempts
        observations.append(
            _observation(
                "model_retry",
                False,
                _semantic_retry_observation(validation_error),
                {"stage": stage, "attempt": attempts},
            )
        )
        if attempts > MAX_BAML_MODEL_RETRIES:
            raise RuntimeError(
                f"BAML context graph returned invalid {stage} output after "
                f"{MAX_BAML_MODEL_RETRIES} retries: {validation_error}"
            )
        validation_feedback = validation_error
        if progress:
            print(f"  context-graph retry {stage} attempt={attempts}", flush=True)


def _validate_links_for_records(
    result: Any,
    *,
    records_by_id: dict[str, dict[str, Any]],
    allowed_pairs: set[tuple[str, str]] | None = None,
) -> str | None:
    """Return semantic validation feedback for generated graph links."""
    seen: set[tuple[str, str, str]] = set()
    for link in _extract_links(result):
        source_id = str(link.get("source_record_id") or "").strip()
        target_id = str(link.get("target_record_id") or "").strip()
        relation_kind = _clean_relation_kind(link.get("relation_kind"))
        if not source_id or not target_id:
            return "graph links must include source_record_id and target_record_id"
        if source_id == target_id:
            return f"graph link {source_id} cannot target itself"
        if source_id not in records_by_id:
            return f"source_record_id {source_id} was not in reviewed records"
        if target_id not in records_by_id:
            return f"target_record_id {target_id} was not in reviewed records"
        if allowed_pairs is not None and tuple(sorted((source_id, target_id))) not in allowed_pairs:
            return f"graph link {source_id}->{target_id} was not in candidate_pairs_json"
        if relation_kind not in SUPPORTED_RELATION_KINDS:
            return f"unsupported relation_kind {relation_kind or '<empty>'}"
        confidence = float(link.get("confidence") or 0.0)
        if confidence < 0.0 or confidence > 1.0:
            return f"confidence for {source_id}->{target_id} must be between 0 and 1"
        if confidence < 0.55:
            return f"confidence for {source_id}->{target_id} is too low to persist"
        evidence_ids = {
            str(record_id or "").strip()
            for record_id in (link.get("evidence_record_ids") or [])
            if str(record_id or "").strip()
        }
        if not evidence_ids:
            return f"graph link {source_id}->{target_id} must include evidence_record_ids"
        if missing := sorted(evidence_ids - set(records_by_id)):
            return f"evidence_record_ids were not reviewed records: {', '.join(missing)}"
        key = (source_id, target_id, relation_kind)
        if key in seen:
            return f"duplicate graph link {source_id}->{target_id}:{relation_kind}"
        seen.add(key)
    return None


def _allowed_pair_set(pairs: list[dict[str, Any]]) -> set[tuple[str, str]]:
    """Return unordered candidate-pair ids accepted for one BAML call."""
    allowed: set[tuple[str, str]] = set()
    for pair in pairs:
        source_id = str(pair.get("source_record_id") or "").strip()
        target_id = str(pair.get("target_record_id") or "").strip()
        if source_id and target_id and source_id != target_id:
            allowed.add(tuple(sorted((source_id, target_id))))
    return allowed


def _extract_links(result: Any) -> list[dict[str, Any]]:
    """Extract normalized link dictionaries from generated BAML output."""
    links: list[dict[str, Any]] = []
    for raw_link in _model_payload(result).get("links") or []:
        link = _model_payload(raw_link)
        relation_kind = _clean_relation_kind(link.get("relation_kind"))
        links.append(
            {
                "source_record_id": str(link.get("source_record_id") or "").strip(),
                "target_record_id": str(link.get("target_record_id") or "").strip(),
                "relation_kind": relation_kind,
                "label": str(link.get("label") or relation_kind).strip(),
                "rationale": str(link.get("rationale") or "").strip(),
                "evidence_record_ids": [
                    str(record_id).strip()
                    for record_id in (link.get("evidence_record_ids") or [])
                    if str(record_id).strip()
                ],
                "confidence": float(link.get("confidence") or 0.0),
            }
        )
    return links


def _dedupe_links(links: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return one highest-confidence link for each directed relation key."""
    best: dict[tuple[str, str, str], dict[str, Any]] = {}
    for link in links:
        key = (
            str(link.get("source_record_id") or ""),
            str(link.get("target_record_id") or ""),
            str(link.get("relation_kind") or ""),
        )
        if not all(key):
            continue
        current = best.get(key)
        if current is None or float(link.get("confidence") or 0.0) > float(current.get("confidence") or 0.0):
            best[key] = link
    return list(best.values())


def _model_payload(value: Any) -> dict[str, Any]:
    """Convert generated BAML objects into plain dictionaries."""
    if hasattr(value, "model_dump"):
        return _plain_value(value.model_dump(exclude_none=True))
    if isinstance(value, dict):
        return _plain_value({key: item for key, item in value.items() if item is not None})
    if value is None:
        return {}
    return _plain_value(getattr(value, "__dict__", {}))


def _plain_value(value: Any) -> Any:
    """Convert enums and generated model values into JSON-like values."""
    if hasattr(value, "value"):
        return value.value
    if isinstance(value, dict):
        return {key: _plain_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_plain_value(item) for item in value]
    return value


def _clean_relation_kind(value: Any) -> str:
    """Normalize generated enum/string relation kinds."""
    enum_value = getattr(value, "value", None)
    text = str(enum_value if enum_value is not None else value or "").strip().lower()
    return text or "related"


def _instruction_with_validation_feedback(run_instruction: str, validation_feedback: str) -> str:
    """Add compact retry feedback to the BAML run instruction."""
    if not validation_feedback:
        return run_instruction
    return (
        f"{run_instruction}\n\n"
        "Previous structured output was unsafe or incomplete. "
        f"Fix this validation error and return a complete corrected link plan: {validation_feedback}"
    )


def _is_recoverable_baml_error(exc: Exception) -> bool:
    """Return whether BAML should be retried for this exception type."""
    return type(exc).__name__ in BAML_RECOVERABLE_ERROR_NAMES


def _model_retry_observation(exc: Exception) -> str:
    """Return compact retry text for model/runtime errors."""
    return f"{type(exc).__name__}: {str(exc)[:500]}"


def _semantic_retry_observation(validation_error: str) -> str:
    """Return compact retry text for semantic validation errors."""
    return f"context_graph_validation_failed: {validation_error}"


def _observation(
    action: str,
    ok: bool,
    content: str,
    args: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build one graph event payload."""
    return {"action": action, "ok": ok, "content": content, "args": args or {}}
