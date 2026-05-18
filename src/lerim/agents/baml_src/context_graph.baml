enum ContextGraphRelationKind {
  SUPPORTS @alias("supports") @description("The source record gives evidence for, confirms, or strengthens the target record.")
  REFINES @alias("refines") @description("The source record narrows, clarifies, or makes the target record more specific.")
  DEPENDS_ON @alias("depends_on") @description("The source record relies on the target record being true or accepted.")
  CONTRADICTS @alias("contradicts") @description("The source record conflicts with the target record and both should be reviewed together.")
  SAME_TOPIC @alias("same_topic") @description("The records are about the same reusable topic but neither replaces the other.")
  EVIDENCE_FOR @alias("evidence_for") @description("The source record is concrete evidence for the target record.")
  SUPERSEDES @alias("supersedes") @description("The source record is the newer or stronger context that replaces the target record.")
  RELATED @alias("related") @description("The records are usefully adjacent for future retrieval, but the relationship is weaker than the other relation kinds.")
}

class ContextGraphLink {
  source_record_id string
  target_record_id string
  relation_kind ContextGraphRelationKind
  label string
  rationale string
  evidence_record_ids string[]
  confidence float
}

class ContextGraphPlan {
  links ContextGraphLink[]
  completion_summary string?
}

function LinkContextRecords(
  run_instruction: string,
  cluster_id: string,
  records_json: string,
  candidate_pairs_json: string,
  existing_edges_json: string
) -> ContextGraphPlan {
  client MiniMaxM27
  prompt #"
    {{ _.role("system") }}
    You are Lerim's context graph linker. You run after noisy agent traces have already been filtered into curated context records.
    Return only structured output. Do not include <think> tags, hidden reasoning, markdown, or prose.
    The top-level output must include links and completion_summary.
    Use an empty links list when no relationship is justified.

    Job:
    - Build useful relationships between curated context records so future agents can navigate decisions, evidence, constraints, preferences, facts, and handoffs.
    - Link records only when the relationship would help retrieval, explanation, review, or handoff quality.
    - Prefer precise relation kinds over generic related.
    - Avoid dense hairball graphs. A small number of high-confidence links is better than many weak links.
    - Sparse does not mean disconnected. In a small curated cluster, leave a record isolated only when none of its candidate pairs has a grounded relationship that would help future navigation.
    - Prefer enough grounded links that a future agent can move between the core rules, their verification gates, and the source-boundary or workflow constraints that enforce them.
    - Use the candidate pairs as the reviewed search space. Do not invent record IDs.
    - Review existing_edges_json as the current graph state for this candidate space.
    - Return existing links again when they are still useful and grounded.
    - Omit existing links only when they are now stale, weak, contradicted, or no longer useful.
    - Keep labels short and business-readable.

    Relationship rules:
    - supports: source strengthens target.
    - evidence_for: source is concrete source evidence for target.
    - depends_on: source relies on target.
    - refines: source makes target more specific or operational.
    - supersedes: source is the stronger newer context and target is weaker or obsolete.
    - contradicts: both records cannot be true without review.
    - same_topic: records share a topic and should be inspected together.
    - related: use only when no stronger relation applies. Do not use related when the pair shares an explicit rule, decision, constraint, dependency, evidence relationship, contradiction, or operational refinement.
    - A workflow, quality, source-boundary, or transport rule can support a release/evaluation/dashboard gate when the gate depends on that rule being enforced.
    - A more specific source-boundary, verification, or transport record can refine a broader quality or no-noise rule.
    - Link source-ingestion, compaction, cleaning, or source-boundary records to control-plane/noise-filtering records when they govern the same boundary: what raw trace content is allowed to become context.
    - Link verification workflow preferences to eval, release-gate, or source-of-truth records when the preference explains how those gates should be exercised.
    - Link transport, persistence, or shipping contracts to dashboard, graph, or observability gates when the contract is required for the visible product surface to be trustworthy.
    - For every returned link, evidence_record_ids should include both linked endpoint IDs unless another supplied record is the only supporting evidence.

    Confidence rules:
    - Use confidence >= 0.75 only for relationships clearly supported by record text.
    - Use confidence between 0.55 and 0.74 for useful but weaker relationships.
    - Omit links below 0.55.

    {{ _.role("user") }}
    RUN INSTRUCTION:
    {{ run_instruction }}

    CLUSTER ID:
    {{ cluster_id }}

    RECORDS JSON:
    {{ records_json }}

    CANDIDATE PAIRS JSON:
    {{ candidate_pairs_json }}

    EXISTING EDGES JSON:
    {{ existing_edges_json }}

    {{ ctx.output_format }}
  "#
}

function ReviewContextGraphLinks(
  run_instruction: string,
  records_json: string,
  proposed_links_json: string
) -> ContextGraphPlan {
  client MiniMaxM27
  prompt #"
    {{ _.role("system") }}
    You are Lerim's context graph reviewer. Review proposed links before they are persisted.
    Return only structured output. Do not include <think> tags, hidden reasoning, markdown, or prose.
    The top-level output must include links and completion_summary.

    Keep only links that are:
    - grounded in the provided record text
    - useful for future agents
    - not duplicates
    - not generic when a stronger relation kind is available
    - not low-confidence adjacency

    Normalize labels to short business-readable phrases.
    Keep evidence_record_ids limited to records that support the link, and include both linked endpoint IDs when both endpoint texts support the relationship.
    Drop weak links rather than preserving them with lower confidence.
    Do not over-prune a small curated cluster: if a proposed link is grounded, useful, and above the confidence floor, keep it even when the graph already has another strong link.

    {{ _.role("user") }}
    RUN INSTRUCTION:
    {{ run_instruction }}

    RECORDS JSON:
    {{ records_json }}

    PROPOSED LINKS JSON:
    {{ proposed_links_json }}

    {{ ctx.output_format }}
  "#
}
