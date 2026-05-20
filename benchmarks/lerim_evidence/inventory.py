"""Inventory of Lerim benchmark evidence surfaces.

The scaffold starts with benchmark inventory and internal sanity checks. It
does not encode a product verdict; it makes each public Lerim claim measurable.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BenchmarkSurface:
    """One benchmark or product-evidence surface for Lerim."""

    key: str
    title: str
    public_claim: str
    lerim_first_measure: str
    default_runner: str
    external_api_required: bool
    notes: str


BENCHMARK_SURFACES: tuple[BenchmarkSurface, ...] = (
    BenchmarkSurface(
        key="longmemeval_s_retrieval_r5",
        title="LongMemEval-S retrieval R@5",
        public_claim="Lerim retrieves the source sessions needed for long-horizon questions.",
        lerim_first_measure=(
            "Evaluate whether Lerim retrieves the expected durable context records "
            "for labeled long-horizon questions."
        ),
        default_runner="longmemeval",
        external_api_required=False,
        notes=(
            "Runner uses the LongMemEval-S cleaned dataset and reports retrieval-only "
            "metrics. It is local/offline by default and is not an official LongMemEval QA score."
        ),
    ),
    BenchmarkSurface(
        key="retrieval_latency",
        title="Retrieval latency",
        public_claim="Lerim context recall is fast enough for agent startup and tool use.",
        lerim_first_measure=(
            "Measure p50/p95/p99 local ContextStore search latency over real "
            "LongMemEval-S session corpora."
        ),
        default_runner="retrieval_latency",
        external_api_required=False,
        notes="Latency runner uses LongMemEval-S sessions; it is local performance evidence, not hosted load testing.",
    ),
    BenchmarkSurface(
        key="context_budget",
        title="Context budget",
        public_claim="Lerim can feed agents compact context instead of replaying full traces.",
        lerim_first_measure=(
            "Compare full session replay tokens against Lerim's retrieved top-K "
            "session window for the same LongMemEval-S question."
        ),
        default_runner="context_budget",
        external_api_required=False,
        notes=(
            "Runner uses LongMemEval-S haystacks and a Hugging Face tokenizer "
            "to compare full replay against Lerim top-K retrieved sessions."
        ),
    ),
    BenchmarkSurface(
        key="auto_capture_coverage",
        title="Auto-capture coverage",
        public_claim="Lerim can capture completed work from supported agent sources.",
        lerim_first_measure=(
            "Inventory supported Lerim adapters and verify import coverage over sample "
            "Codex, Claude, Cursor, and OpenCode traces."
        ),
        default_runner="inventory",
        external_api_required=False,
        notes="This is a product-surface benchmark, not an LLM quality benchmark.",
    ),
    BenchmarkSurface(
        key="session_replay_import",
        title="JSONL session replay/import",
        public_claim="Lerim can import user-owned JSONL source sessions.",
        lerim_first_measure=(
            "Run trace importer paths over local fixtures and verify persisted "
            "session plus record provenance."
        ),
        default_runner="internal_sanity",
        external_api_required=False,
        notes="Internal sanity uses direct ContextStore provenance writes; importer fixtures can be added later.",
    ),
    BenchmarkSurface(
        key="consolidation_quality",
        title="Raw-to-semantic consolidation quality",
        public_claim="Lerim keeps durable context compact, deduplicated, and auditable.",
        lerim_first_measure=(
            "Use existing context curator expectations for duplicate handling, obsolete "
            "records, active record budget, and version history."
        ),
        default_runner="inventory",
        external_api_required=True,
        notes="Full curation scoring is LLM-backed and should stay opt-in.",
    ),
    BenchmarkSurface(
        key="knowledge_graph",
        title="Knowledge graph extraction",
        public_claim="Lerim can link related decisions, facts, constraints, and handoffs.",
        lerim_first_measure=(
            "Measure context graph node and edge generation from active curated records "
            "with fixed expected relation fixtures."
        ),
        default_runner="inventory",
        external_api_required=True,
        notes="Graph agent execution is model-backed, so default local sanity only reports inventory.",
    ),
    BenchmarkSurface(
        key="mcp_and_api_surface",
        title="MCP and HTTP API surface",
        public_claim="Lerim exposes useful local tools for context recall and trace submission.",
        lerim_first_measure=(
            "Inventory Lerim CLI/API capabilities that are relevant to memory capture, "
            "query, curation, and observability."
        ),
        default_runner="inventory",
        external_api_required=False,
        notes="Counts alone are weak; report capability groups before raw endpoint totals.",
    ),
    BenchmarkSurface(
        key="observability",
        title="Observability and auditability",
        public_claim="Lerim keeps evidence and audit history for learned context.",
        lerim_first_measure=(
            "Report MLflow trace/eval artifacts, record_versions audit history, and "
            "runtime status surfaces."
        ),
        default_runner="internal_sanity",
        external_api_required=False,
        notes="Internal sanity verifies version history exists for created context records.",
    ),
    BenchmarkSurface(
        key="local_runtime_dependencies",
        title="Local runtime dependencies",
        public_claim="Lerim core works from local stores without requiring a hosted service.",
        lerim_first_measure=(
            "Report Lerim's local SQLite context/index stores and optional provider "
            "boundaries without external calls."
        ),
        default_runner="internal_sanity",
        external_api_required=False,
        notes="This is inventory/reporting, not a quality score.",
    ),
)


def surfaces_by_runner(default_runner: str) -> tuple[BenchmarkSurface, ...]:
    """Return benchmark surfaces that use one default runner label."""
    return tuple(
        surface for surface in BENCHMARK_SURFACES if surface.default_runner == default_runner
    )
