enum RecordKind {
  DECISION @alias("decision") @description("A durable project decision with decision and why fields.")
  PREFERENCE @alias("preference") @description("A stable user or workflow preference.")
  CONSTRAINT @alias("constraint") @description("A durable user/product policy invariant, source-ingestion boundary, limit, prohibition, or must/cannot rule; not a runtime setup, path, access, dependency, or environment fact.")
  FACT @alias("fact") @description("A durable project fact, setup truth, dependency, path, access, runtime requirement, or environment requirement; not a required/prohibited product behavior or source-ingestion boundary.")
  REFERENCE @alias("reference") @description("A pointer to an external source of truth.")
}

enum RecordStatus {
  ACTIVE @alias("active") @description("Current context that future sessions may reuse.")
  ARCHIVED @alias("archived") @description("Historical or routine context that should not be treated as active guidance.")
}

enum CardType {
  DECISION @alias("decision") @description("User-facing decision card; use with kind decision.")
  CONSTRAINT @alias("constraint") @description("User-facing constraint card; use when no narrower workflow card fits.")
  HANDOFF @alias("handoff") @description("Pending next-owner workflow card for an open work item. Preserve the exact item identifier when scoped, required verification, pending state, and destination/owner/route.")
  SOURCE_OF_TRUTH @alias("source_of_truth") @description("Authoritative source future agents should consult directly because the answer is unresolved, changing, or not fully stated in the trace. Keep the source, current answer, owner, route, and authority boundary together when they form one reusable source-of-truth rule. Do not use when the trace already states the applicable rule and the source only supports that rule.")
  FAILED_PATH @alias("failed_path") @description("Tried path or hypothesis future agents should not repeat.")
  REPEATED_WASTE @alias("repeated_waste") @description("Recurring avoidable work pattern. Requires evidence of recurrence or a likely repeated future action, not one stale lookup or isolated source conflict.")
  GUARDRAIL_CANDIDATE @alias("guardrail_candidate") @description("Candidate product or workflow guardrail requiring review. Use kind fact unless the source says the guardrail is already approved as an active gate.")
  KNOWN_FIX @alias("known_fix") @description("Reusable fix or playbook step that worked.")
  ESCALATION @alias("escalation") @description("Escalation condition and destination.")
  RUNBOOK_GAP @alias("runbook_gap") @description("Missing, wrong, or insufficient runbook coverage. Include the required follow-up or guardrail in this card when it is the same missing coverage. Use kind fact unless the source establishes an approved workflow constraint.")
  CUSTOMER_CONSTRAINT @alias("customer_constraint") @description("Customer-facing approval, privacy, compliance, no-promise, or policy boundary. For one customer-facing outcome, keep related thresholds, verification, evidence, approval, and no-promise limits together in one card; do not emit one-condition fragments.")
  ROOT_CAUSE @alias("root_cause") @description("Confirmed root cause, not a hypothesis. Include the confirmed mitigation when it is part of the same causal chain.")
  MITIGATION @alias("mitigation") @description("Mitigation that reduced impact or restored service. Use as a separate card only when the mitigation is reusable without the root-cause card.")
  REJECTED_HYPOTHESIS @alias("rejected_hypothesis") @description("Hypothesis ruled out by evidence.")
  POLICY_REFERENCE @alias("policy_reference") @description("Policy or playbook source that must be consulted directly because the needed answer is unresolved or changing; do not use for ordinary evidence supporting a captured rule.")
  PRODUCT_BEHAVIOR @alias("product_behavior") @description("Stable observed product behavior or customer-visible behavior.")
  OWNER_DECISION @alias("owner_decision") @description("Durable owner or authority boundary. Use kind constraint when it imposes a required future route, owner, approval, or rollback authority; use kind fact for descriptive ownership only.")
  FOLLOW_UP_RISK @alias("follow_up_risk") @description("Future risk or follow-up that remains actionable. Use sparingly; fold into root_cause, runbook_gap, handoff, or guardrail cards when it is the same work.")
  REPO_CONVENTION @alias("repo_convention") @description("Repository convention future coding agents should follow.")
  ARCHITECTURE_DECISION @alias("architecture_decision") @description("Architecture-level decision or boundary.")
  SETUP_FACT @alias("setup_fact") @description("Stable setup, dependency, access, path, or environment fact.")
  TEST_LESSON @alias("test_lesson") @description("Reusable lesson from testing or debugging.")
  RELEASE_HANDOFF @alias("release_handoff") @description("Release-specific handoff or readiness boundary.")

  @@description("Product-facing workflow card. This is separate from RecordKind.")
}

enum LifecycleStatus {
  PROPOSED @alias("proposed")
  APPROVED @alias("approved")
  ACTIVE @alias("active")
  NEEDS_REVIEW @alias("needs_review")
  SUPERSEDED @alias("superseded")
  RETIRED @alias("retired")
  REJECTED @alias("rejected")
}

enum ApprovalStatus {
  PENDING @alias("pending")
  APPROVED @alias("approved")
  REJECTED @alias("rejected")
}

class DurableFinding {
  theme string @description("Short stable theme for this finding.")
  kind RecordKind @description("Storage ontology for the durable finding. Use decision, preference, constraint, fact, or reference. Do not use workflow card names here.")
  card_type CardType? @description("Optional product-facing workflow card shape from the source profile output_cards, such as handoff, failed_path, source_of_truth, customer_constraint, or runbook_gap.")
  line int? @description("1-based supporting line when the window gives one.")
  quote string? @description("Short supporting quote from the current window.")
  note string @description("Compact semantic finding. Avoid action logs and copied errors.")
}

class ImplementationFinding {
  theme string @description("Short theme for source-session-local evidence or noise.")
  line int? @description("1-based supporting line when the window gives one.")
  quote string? @description("Short supporting quote from the current window.")
  note string @description("Compact note explaining why this is only execution evidence, a discarded hypothesis, or local support.")
}

class SourceWindowScan {
  episode_update string? @description("Compact update for the final episode summary. May be omitted when this window adds nothing.")
  durable_findings DurableFinding[] @description("Reusable decisions, preferences, constraints, facts, and references found in this window.")
  implementation_findings ImplementationFinding[] @description("Implementation evidence, discarded hypotheses, and local details useful only as support/noise.")
  discarded_noise string[] @description("Short descriptions of noisy categories intentionally not saved.")
}

class SignalFilterResult {
  kept_durable_findings DurableFinding[] @description("Durable findings that passed the final reuse and dedupe filter.")
  rejected_findings DurableFinding[] @description("Candidate durable findings rejected as weak, duplicate, source-local, or implementation-only.")
  filtering_summary string? @description("Compact explanation of the filtering decision.")
}

class EpisodeDraft {
  title string? @description("Optional short title for the current-session episode. Runtime derives one if omitted.")
  body string? @description("Compact episode body. If omitted, runtime builds it from user_intent and what_happened.")
  status RecordStatus? @description("Use archived for routine/no-durable sessions; active only when the episode itself remains useful.")
  user_intent string? @description("What the user wanted in this source session. Runtime derives a generic value if omitted.")
  what_happened string? @description("What the session actually did. Runtime derives a generic value if omitted.")
  outcomes string? @description("Optional concise outcome.")
  source_event_refs string[] @description("Required array of trace line refs that support this episode, for example line:12. Use [] only when no source line exists; never return null.")
  evidence_refs string[] @description("Required array of short evidence refs or quotes that support this episode. Use [] when no evidence ref is available; never return null.")
}

class DurableRecordDraft {
  kind RecordKind @description("Durable record kind.")
  card_type CardType? @description("Product-facing card shape. Pick from the source profile output cards when possible.")
  title string @description("Short standalone durable title.")
  body string @description("Compact standalone durable body.")
  status RecordStatus? @description("Use active for every new reusable durable record. Do not set archived on durable_records.")
  lifecycle_status LifecycleStatus? @description("Review lifecycle. Workflow cards should usually be proposed unless already approved by source evidence.")
  approval_status ApprovalStatus? @description("Human review state for the card.")
  confidence float? @description("Optional source-supported confidence from 0.0 to 1.0.")
  review_notes string?
  valid_from string?
  valid_until string?
  superseded_by string?
  decision string?
  why string?
  alternatives string?
  consequences string?
  source_event_refs string[] @description("Trace line refs that directly support this durable record, for example line:12. Use [] only when no source line is available.")
  evidence_refs string[] @description("Short evidence refs or quotes that directly support this durable record. Include the policy, playbook, runbook, ticket, case, incident, or line reference when it supports this exact record.")
}

class DurableRecordUpdateDraft {
  record_id string @description("Exact existing record_id from the existing record manifest.")
  kind RecordKind @description("Durable record kind.")
  card_type CardType? @description("Product-facing card shape. Pick from the source profile output cards when possible.")
  title string @description("Complete replacement title.")
  body string @description("Complete replacement body.")
  status RecordStatus?
  lifecycle_status LifecycleStatus?
  approval_status ApprovalStatus?
  confidence float?
  review_notes string?
  valid_from string?
  valid_until string?
  superseded_by string?
  decision string?
  why string?
  alternatives string?
  consequences string?
  change_reason string?
  source_event_refs string[] @description("Trace line refs that directly support this update, for example line:12. Use [] only when no source line is available.")
  evidence_refs string[] @description("Short evidence refs or quotes that directly support this update. Include the policy, playbook, runbook, ticket, case, incident, or line reference when it supports this exact update.")
}

class SynthesizedContextRecords {
  episode EpisodeDraft @description("Exactly one current-session episode record draft.")
  durable_records DurableRecordDraft[] @description("Zero or more durable records.")
  record_updates DurableRecordUpdateDraft[] @description("Zero or more complete updates to existing durable records.")
  completion_summary string? @description("Brief summary of ingestion work for final_result/reporting.")
}

function ObserveSourceWindow(
  run_instruction: string,
  source_profile_context: string,
  prior_episode_summary: string,
  prior_findings_summary: string,
  source_window: string
) -> SourceWindowScan {
  client MiniMaxM27
  prompt #"
    {{ _.role("system") }}
    You are Lerim's source-session observer. Scan one window from an agent activity stream for context ingestion.
    Return only structured output. Do not save records and do not plan future tool calls.
    Do not include <think> tags, hidden reasoning, markdown, or prose.
    The top-level output must include episode_update, durable_findings, implementation_findings, and discarded_noise.
    Use an empty string or empty list when a field has no content.
    Every durable_findings item must be an object with:
    - theme
    - kind: one of decision, preference, constraint, fact, or reference
    - note
    - optional card_type from the source profile output_cards, such as handoff, customer_constraint, source_of_truth, failed_path, rejected_hypothesis, runbook_gap, or guardrail_candidate
    - optional line
    - optional quote
    Every implementation_findings item must be an object with theme, note, and optional line or quote.
    Never return finding items as plain strings.
    Never use source profile card names as kind values. Handoff, escalation, customer_constraint, failed_path, root_cause, source_of_truth, and runbook_gap are card_type values, not record kind values.

    Separate:
    - episode_update: what happened in this session window, for the final episode record.
    - durable_findings: reusable project/user context only.
    - implementation_findings: local execution evidence, transient actions, discarded hypotheses, or support.
    - discarded_noise: categories of content intentionally ignored.

    Durable signal means a decision, preference, constraint, fact, or reference likely useful beyond this source session.
    Implementation detail alone is not durable signal.
    A durable finding should help a future agent make a better decision in a new chat.
    Save what a future agent would be relieved to already know: stable user preferences, chosen policies, durable constraints, source-of-truth references, and stable project or product truths.
    For workflow traces, use card_type for the profile-specific card shape while keeping kind in the storage ontology.
    A policy, playbook, runbook, catalog, or source mention is evidence unless the future action is to consult that source for unresolved or changing details.
    Merge thresholds, prerequisites, evidence requirements, verification steps, approval gates, and no-promise limits into the policy or workflow card they govern.
    When the source profile lists handoff as an output card, keep a standing behavior boundary separate from a scoped open-item handoff only when both independently change future behavior.
    A scoped handoff is durable only for profiles that list handoff when the source names the open item plus a pending next action, prerequisite, owner, destination, route, or no-action boundary. Preserve the item id and pending state; do not create extra prerequisite fragments.
    Failed paths, rejected hypotheses, mitigations, and runbook gaps are durable only when they prevent repeated waste or change a future action.
    Session-control instructions, injected scaffolding, assistant/tool behavior rules, local debug steps, audits, reviews, eval findings, dashboard checks, and historical workspace status are implementation evidence unless a user-authored source explicitly turns them into a standing product rule, preference, durable requirement, or source-of-truth pointer.
    No-save instructions about local or one-run artifacts only filter this source session; do not turn them into durable facts, preferences, noise policies, or episode text.
    Classify stable runtime setup, dependency, access, path, source, or environment requirements as facts unless the source establishes a product or business-process constraint.
    Classify durable product, data-model, customer-policy, and workflow invariants as constraints when they limit what future work may do.
    When a window mixes durable signal with local evidence, put only the reusable point in durable_findings and supporting local evidence in implementation_findings.
    Use semantic meaning, not exact wording. Do not copy long artifacts, logs, raw errors, or tool transcripts.
    Do not carry incidental personal names, direct address labels, or conversational identity markers into episode updates or findings unless the identity itself is the durable context. Prefer role-neutral wording such as "the user" and "the assistant".
    If the window has no durable signal, return an empty durable_findings list.
    If the window adds nothing meaningful to the episode, episode_update may be an empty string.

    {{ _.role("user") }}
    RUN INSTRUCTION:
    {{ run_instruction }}

    SOURCE PROFILE:
    {{ source_profile_context }}

    Use this profile to decide which reusable signals matter. Signal types and output cards are vocabulary, not a checklist. Do not create findings outside this profile unless the source clearly contains a generic durable decision, constraint, fact, preference, or reference.

    PRIOR EPISODE SUMMARY:
    {{ prior_episode_summary }}

    PRIOR FINDINGS SUMMARY:
    {{ prior_findings_summary }}

    SOURCE SESSION WINDOW:
    {{ source_window }}

    {{ ctx.output_format }}
  "#
}

function FilterDurableSignal(
  run_instruction: string,
  source_profile_context: string,
  episode_summary: string,
  durable_findings_summary: string,
  implementation_summary: string,
  existing_record_manifest: string
) -> SignalFilterResult {
  client MiniMaxM27
  prompt #"
    {{ _.role("system") }}
    You are Lerim's durable-signal filter.
    Return only structured output. Do not include <think> tags, hidden reasoning, markdown, or prose.
    The top-level output must include kept_durable_findings, rejected_findings, and filtering_summary.
    Use empty lists when no candidates pass or no candidates are rejected.
    Every kept_durable_findings and rejected_findings item must be an object with:
    - theme
    - kind: one of decision, preference, constraint, fact, or reference
    - note
    - optional card_type from the source profile output_cards
    - optional line
    - optional quote
    Never use source profile card names as kind values. Handoff, escalation, customer_constraint, failed_path, root_cause, source_of_truth, and runbook_gap are card_type values, not record kind values.

    Keep only durable signal that would change what a future agent does in a separate session.
    Reject implementation evidence, generic domain knowledge, session-control instructions, local tool actions, one-time audits/reviews/eval findings, stale status observations, no-save instructions, duplicates, and weak inferences.
    Preserve card_type when it captures a profile-supported workflow shape. Reject invalid kind values instead of repairing them.
    Keep card_type values inside the source profile Output cards. If a candidate uses a card type outside that profile, reject or rewrite the finding to a supported card type rather than keeping the unsupported card type.
    Keep evidence-backed workflow cards when they preserve a future action: route, owner, source, failed path, mitigation, rejected hypothesis, verification requirement, runbook gap, escalation, or resumable handoff.
    Signal types and output cards are vocabulary, not a checklist. Prefer the fewest durable findings that preserve all future-action value.
    Reject bare queue, priority, label, or owner metadata that has no next action.
    A scoped handoff is durable only for profiles that list handoff and when it names the open item plus pending next action, prerequisite, owner, destination, route, or no-action boundary.
    Do not reject a named open-item handoff as implementation evidence merely because it is case-scoped when the profile lists handoff. A case-scoped handoff with pending next action, prerequisite, owner, destination, route, or no-action boundary is durable resumable workflow context for those profiles.
    A scoped handoff is not a duplicate of the standing policy it applies; keep both when the profile lists handoff and the policy and handoff independently change future behavior.
    Keep the item identifier for a scoped handoff so a future agent can resume the correct work.
    Fold thresholds, prerequisites, verification, evidence requirements, approval gates, and policy citations into the workflow or policy finding they govern.
    Keep a standing policy boundary separate from a scoped open-item handoff only when the profile lists handoff and both are independently useful after filtering.
    Treat policy, playbook, catalog, runbook, and service-catalog mentions as evidence unless the future action is to consult that source later for unresolved or changing details.
    Classify runtime setup, dependency, access, path, source, and environment requirements as facts. Classify product, business-process, customer-policy, and workflow invariants as constraints.
    Existing records are duplicate-risk context. Keep corrections or completions only when the source adds durable value to a manifest record.
    If no candidate passes this bar, return an empty kept_durable_findings list.

    {{ _.role("user") }}
    RUN INSTRUCTION:
    {{ run_instruction }}

    SOURCE PROFILE:
    {{ source_profile_context }}

    Use this profile to prioritize reusable signals, reject workflow-specific noise, and preserve the generic durable-signal bar.

    EXISTING RECORD MANIFEST:
    {{ existing_record_manifest }}

    EPISODE SUMMARY:
    {{ episode_summary }}

    CANDIDATE DURABLE FINDINGS:
    {{ durable_findings_summary }}

    IMPLEMENTATION AND NOISE FINDINGS:
    {{ implementation_summary }}

    {{ ctx.output_format }}
  "#
}

function SynthesizeContextRecords(
  run_instruction: string,
  source_profile_context: string,
  episode_summary: string,
  durable_findings_summary: string,
  existing_record_manifest: string
) -> SynthesizedContextRecords {
  client MiniMaxM27
  prompt #"
    {{ _.role("system") }}
    You are Lerim's context writer. Synthesize final context records from filtered source-session findings.
    Return only structured output.
    Do not include <think> tags, hidden reasoning, markdown, or prose.
    The top-level output must include episode, durable_records, record_updates, and completion_summary.
    Use an empty durable_records list when there is no durable signal.
    Use an empty record_updates list when no existing record should be updated.
    Every durable_records item must be an object with kind, card_type, title, and body when a product card type is supported by the source profile.
    Every record_updates item must include an exact record_id from EXISTING RECORD MANIFEST plus a complete replacement durable payload.
    Optional durable record fields are status, lifecycle_status, approval_status, confidence, review_notes, valid_from, valid_until, superseded_by, decision, why, alternatives, consequences, source_event_refs, and evidence_refs.
    Because source_event_refs and evidence_refs are arrays, return [] when no value is available.
    Every durable_records and record_updates item should include source_event_refs when the durable finding gives line evidence. Use refs like "line:42".
    Do not invent line refs. If no direct line is available, include a concise evidence_refs entry from the supporting finding instead.
    Evidence refs must describe the actual source in the trace, not an inferred confirmation, contact, approval, or authority event.
    Never return durable_records items as plain strings or as generic type/record objects.

    Create exactly one episode record for the current session. Episode records are trace history, not durable guidance.
    If durable_records or record_updates are non-empty, archive the episode and keep it as compact provenance for the original source activity.
    Episode fields must not describe Lerim ingestion work or turn planned, requested, or pending steps into completed outcomes.
    If there is no durable signal, create an archived episode and do not save discarded material in any field.

    Write durable_records only from DURABLE FINDINGS that passed the filter, except for one minimal recovery record/update when the episode summary explicitly contains a missed durable signal.
    Never create durable records from run instructions, ingestion guidance, existing-record text, advisory reports, session-control instructions, or implementation-only evidence.
    Update an existing durable record instead of creating a duplicate when the manifest shows the same claim and the source adds durable value.
    record_updates must target exact record IDs shown in EXISTING RECORD MANIFEST.

    Durable output should be compact, standalone, evidence-backed, and minimal.
    Optimize for the smallest set of records a future agent would be glad to read.
    For one short source session, one to three durable records is usually enough; exceed that only for separate future workflows that remain useful independently.
    Create multiple records only when each one would independently change future behavior.
    Do not split a single reusable workflow into separate "what happened", "what source said", and "what to do" cards when one standalone card can preserve the full boundary.
    Merge prerequisites, thresholds, evidence requirements, verification steps, approval gates, policy citations, and application guidance into the workflow or policy card they govern.
    If one policy source gives several conditions for the same customer-facing workflow outcome, write one customer_constraint record that contains those conditions.
    If candidate records split one policy into threshold-only, verification-only, citation-only, or no-promise-only fragments, merge them into the customer-facing workflow card before returning.
    Never return two customer_constraint records for the same policy source, claim type, approval flow, privacy flow, or customer-facing outcome; merge them into one complete card.
    Keep a behavior-limiting policy boundary separate from a scoped handoff or route only when the profile lists handoff and both are independently useful.
    A scoped handoff should name the work item, preserve pending state, and include the next owner, destination, route, prerequisite, or no-action boundary.
    When the source contains a pending next-agent action for an open work item and the profile lists handoff, keep that scoped handoff as the handoff record; do not replace it with a generic policy-reference or source-of-truth card.
    If the source contains both a standing policy boundary and a named open work item with a pending next action or route, output both only when the profile lists handoff: one merged policy card and one scoped handoff card.
    A named open-item handoff is independently useful even when it repeats the policy boundary only for profiles that list handoff; otherwise keep case-specific handoff details in the archived episode or evidence.
    Do not use handoff for generic answer guidance, citation guidance, or optional escalation advice unless a specific open work item has a pending next owner, route, prerequisite, or no-action boundary.
    Treat source documents as evidence unless the future action is to consult that source later for unresolved or changing details.
    If a source-of-truth lookup already gives the current owner, rule, route, or authority boundary, keep those together in one reference record instead of creating extra owner or routing records for the same boundary.
    If that same reference record already says which local source not to use, do not create a separate failed_path record for the same source-boundary contrast.
    For incident records, merge confirmed mitigation into the root-cause card when they are one causal chain. Merge runbook gaps and the matching follow-up guardrail into one runbook_gap card. Keep rejected hypotheses or failed paths separate only when they would independently prevent likely repeated work.
    For support records, merge product behavior, privacy or approval constraints, and source citations into the customer-facing workflow card they govern unless the source must be consulted directly later.
    Preserve customer-facing privacy, secure-channel, approval, no-promise, and verification boundaries as customer_constraint records when they appear; do not replace them with repeated_waste or source notes.
    Do not save stale-note, old-doc, or conflicting-source failed paths when the surviving card already captures the authoritative source or customer-facing rule to use instead.
    Keep the source's exact scope, threshold, segment, condition, route, owner, and claim type. Do not broaden the rule.

    Classify each durable point once:
    - decision requires an explicit chosen approach and supported why; do not use decision for advice, failed paths, owner routing, or policy rules.
    - preference is stable user or workflow guidance.
    - constraint is a durable product, data-model, business-process, customer-policy, source-boundary, or workflow invariant.
    - fact is durable setup, dependency, access, path, source, environment, root-cause, failed-path, mitigation, rejected-hypothesis, or other stable truth.
    - reference is a source future agents should consult later and must answer both where to look and when to consult it.

    Writing rules:
    - Use card_type for the profile-specific product card and kind for the storage ontology.
    - Do not map card_type names into kind.
    - Set why, alternatives, and consequences to null unless the source explicitly supports them.
    - Do not add rationale, compliance, audit, governance, risk, or enterprise-safety language unless the source states it.
    - Do not include raw errors, command output, repair recipes, local debug steps, incidental personal names, or source-session contrast text.

    Record types:
    - preference: Stable workflow guidance from the user. Save corrections and confirmed non-obvious working style that should carry into future sessions.
    - decision: A chosen approach or project rule that future work should follow and that is not obvious from available artifacts alone. If the source session does not support a durable why, do not use decision.
    - constraint: A durable user/product policy invariant, limit, prohibition, or must/cannot rule that future work must respect. Do not use for runtime setup, path, access, dependency, or environment facts.
    - fact: A durable project fact such as a dependency, runtime setup requirement, path requirement requirement, access requirement, environment requirement, stakeholder driver, or other non-obvious truth.
    - reference: A pointer to an external dashboard, document, ticket system, or other source of truth outside the local workspace. Use reference only when the enduring value is where to look later.
    - customer_constraint, handoff, and escalation cards should use kind constraint.
    - product_behavior, failed_path, known_fix, root_cause, rejected_hypothesis, repeated_waste, runbook_gap, and guardrail_candidate cards should use kind fact unless the source states they are approved active workflow gates.
    - owner_decision cards should use kind constraint when they impose a required future route, owner, approval, or rollback authority; use kind fact for descriptive ownership only.
    - source_of_truth and policy_reference cards should use kind reference.
    - failed_path: Usually kind fact when it records what failed, or kind constraint when it prohibits a repeated action; not kind decision.
    - guardrail_candidate: Usually kind fact because it is a candidate requiring review; use kind constraint only when the source says the guardrail is already approved as an active gate.

    {{ _.role("user") }}
    RUN INSTRUCTION:
    {{ run_instruction }}

    SOURCE PROFILE:
    {{ source_profile_context }}

    Use this profile's output_cards to choose card_type. Output cards are vocabulary, not a checklist. Keep record kind as the storage ontology and card_type as the user-facing workflow shape.
    If a durable finding includes card_type, preserve it unless it conflicts with the source. Do not map card_type names into kind. For example, a handoff card can be kind constraint, a failed_path card can be kind fact, and a source_of_truth card can be kind reference.
    Merge prerequisites, thresholds, required evidence, required verification, and promise or commitment limits into the policy or workflow card they govern. Keep a separate handoff, escalation, owner, failed_path, or source_of_truth card only when it remains independently actionable in a future session.
    Do not write a separate known_fix, policy_reference, product_behavior, or source_of_truth card when it is only a prerequisite or source citation for another durable rule. Fold that detail into the stronger card.
    Do not write a source_of_truth or policy_reference record when the source's complete applicable rule is already captured in a boundary, handoff, escalation, owner, or workflow record.
    A mandatory route, owner handoff, or verification-gated workflow should be kind constraint when it tells future agents what they must or must not do. Use kind fact only for descriptive or advisory workflow knowledge.
    A handoff with a required route, approval gate, verification gate, or no-promise/no-action boundary is a constraint. Use fact for a handoff only when the source describes an already-known routing fact without requiring future behavior.
    When a source_of_truth answer includes its route, owner, authority, or channel, keep those together in one reference/source_of_truth record unless the route remains independently actionable without re-reading the source.
    Preserve service, catalog, source, and runbook identifiers inside a workflow card when they identify the reusable route or authority. Keep ticket, case, incident, and other source-local identifiers out of active reusable card titles and bodies unless the card is explicitly scoped to that exact ongoing item.
    When a workflow card is scoped to an exact ongoing item, include the item identifier in the title or body and preserve whether the handoff is prepared, requested, completed, or blocked.
    Episode text must describe the original source-domain activity, not the ingestion output. Do not say the episode "created", "saved", "extracted", "established constraints", "created records", or "identified durable context".
    Preserve the action state exactly: requested evidence is not verified evidence, a prepared handoff is not a completed route, an advised escalation is not a completed escalation, and an investigated issue is not automatically resolved.
    Do not infer that a prerequisite, verification, approval, route, escalation, or handoff is complete unless the source explicitly says it completed. If the source says the step is required, requested, planned, prepared, or next, preserve that pending state.

    EXISTING RECORD MANIFEST:
    {{ existing_record_manifest }}

    EPISODE SUMMARY:
    {{ episode_summary }}

    DURABLE FINDINGS:
    {{ durable_findings_summary }}

    {{ ctx.output_format }}
  "#
}

function ReviewSynthesizedContextRecords(
  run_instruction: string,
  source_profile_context: string,
  durable_findings_summary: string,
  existing_record_manifest: string,
  synthesized_records_json: string
) -> SynthesizedContextRecords {
  client MiniMaxM27
  prompt #"
    {{ _.role("system") }}
    You are Lerim's final context quality gate. Review synthesized context records before persistence.
    Return only corrected structured output.
    Do not include <think> tags, hidden reasoning, markdown, or prose.
    The top-level output must include episode, durable_records, record_updates, and completion_summary.
    Keep the episode concise; keep episode body under 420 characters.
    Episode records are trace history, not durable guidance. When durable_records or record_updates are non-empty, set episode.status to archived. Use active only when there are no durable_records or record_updates and the episode itself has reusable value that is not already captured by durable records.
    Keep episode.title under 64 characters. Use a short noun phrase, not a recap sentence.
    Episode fields must describe the original source session, not Lerim's ingestion work. Rewrite episodes that mainly describe extracted records, created records, filtering, scanning, or synthesis into a concise source-session summary.
    When durable records exist, keep the episode as compact source-session provenance. Do not repeat every durable rule in the episode; mention the source activity and pending state briefly, and let durable_records carry reusable policy or workflow guidance.
    Episode fields must not turn identified next steps into completed outcomes. If the source only identified, prepared, or recommended a handoff, diagnostic, escalation, or route, say that; do not say the case was escalated, routed, or diagnostics were collected unless the source says that happened.
    Preserve the action state exactly: requested evidence is not verified evidence, a prepared handoff is not a completed route, an advised escalation is not a completed escalation, and an investigated issue is not automatically resolved.
    If an episode is active only because durable records were created, change it to archived.
    Remove discarded noise, rejected findings, no-save categories, source-local acknowledgments, and implementation-only details from every saved field.
    If DURABLE FINDINGS is "(none)" and the synthesized episode mainly names discarded material, rewrite it to a generic archived no-reusable-context episode.
    Preserve source_event_refs and evidence_refs when they directly support a surviving durable record or update.
    Use [] for missing source_event_refs or evidence_refs. Do not invent line refs. Never return null for episode, durable record, or update source_event_refs or evidence_refs.
    Do not leave evidence_refs empty on a durable record when the source text provides a direct policy, playbook, runbook, ticket, case, incident, quote, or line reference for that record.
    Evidence refs must name what the trace actually provided. Do not invent confirmations, approvals, consultations, or contacts that are not in the trace.
    Handoff records scoped to an exact ongoing work item must preserve the item identifier and evidence for the route/state, while still avoiding unrelated private details.

    Correct these issues aggressively:
    - Merge duplicates, overlapping records, and workflow fragments that must be read together.
    - Prefer the fewest records that preserve all durable future-action value.
    - If a single short incident or support case produces more than three durable records, merge lower-grain fragments before returning unless there are truly separate future workflows.
    - Do not split one workflow boundary into separate source, owner, route, prerequisite, and action cards unless each card remains independently useful without the others.
    - Remove records derived from ingestion guidance, run instructions, advisory reports, session-control context, implementation-only details, one-time audits, or historical status observations.
    - Preserve good records when they already satisfy the schema and quality rules.
    - Keep profile card types independent from record kind.
    - Keep a scoped handoff when the profile lists handoff and it preserves a resumable open item, pending state, prerequisite, and route or owner.
    - Keep a standing policy boundary separate from a scoped handoff or route only when the profile lists handoff and both are source-supported and independently useful.
    - Fold thresholds, verification, evidence requirements, no-promise limits, and policy citations into the card they govern.
    - Merge policy fragments from the same source when they govern one customer-facing workflow outcome.
    - Merge threshold-only, verification-only, citation-only, and no-promise-only fragments into one customer_constraint when they govern the same customer-facing outcome.
    - Remove additional customer_constraint records for the same policy source, claim type, approval flow, privacy flow, or customer-facing outcome after merging.
    - Remove source/reference records that only cite evidence for a surviving workflow or boundary record.
    - Collapse a source-of-truth lookup and its owner, route, authority, or channel into one reference record unless the source establishes a separate independently actionable boundary.
    - Remove separate failed_path records when the surviving source_of_truth record already says which stale source or path must not be used.
    - Collapse root cause and mitigation into one root_cause card when they describe the same incident mechanism and recovery.
    - Collapse runbook gaps and their matching follow-up guardrails into one runbook_gap card.
    - Do not keep separate mitigation, follow_up_risk, or guardrail_candidate records when their whole value is already included in a root_cause or runbook_gap card.
    - Collapse product behavior and customer-facing handling constraints into one customer workflow card when both are needed to answer the same support request.
    - Restore a missing customer_constraint when the source has a customer-facing privacy, secure-channel, approval, no-promise, or verification boundary.
    - Restore a missing handoff only when the profile lists handoff and the source has a named open work item with pending next action, prerequisite, owner, route, or no-action boundary.
    - For profiles that do not list handoff, keep named open-item handoff details in the episode or evidence instead of creating a durable handoff card.
    - Remove handoff records that only contain generic source-citation, answer, or optional escalation guidance without a specific open work item and pending route/state.
    - Remove stale-source or old-note failed_path records when the remaining card already tells future agents which authoritative rule or source to use.
    - Keep a scoped handoff when the profile lists handoff and it names an open item plus pending next action and route; do not replace it with only a generic policy record.
    - Classify runtime setup, dependency, access, path, source, and environment requirements as facts; classify product, business-process, customer-policy, source-boundary, and workflow invariants as constraints.
    - Fix impossible kind/card pairs before returning, such as fact/customer_constraint, decision/failed_path, constraint/guardrail_candidate for an unapproved candidate, or reference/handoff.
    - Remove unsupported why, alternatives, consequences, broadening language, and enterprise-sounding rationale.
    - Keep exact source scope, threshold, segment, condition, route, owner, item id, and claim type.
    - durable_records and record_updates must not duplicate the same core claim.
    - record_updates must target exact IDs from EXISTING RECORD MANIFEST.
    - If DURABLE FINDINGS is "(none)", durable_records must be empty unless there is exactly one explicit episode-supported recovery signal.

    {{ _.role("user") }}
    RUN INSTRUCTION:
    {{ run_instruction }}

    SOURCE PROFILE:
    {{ source_profile_context }}

    Verify that durable records keep record kind and card type separate. Keep card_type aligned with the source profile output_cards unless a generic card is clearly better supported.
    The episode should be a short source-session summary of the original activity, not a description of extraction work.

    EXISTING RECORD MANIFEST:
    {{ existing_record_manifest }}

    DURABLE FINDINGS:
    {{ durable_findings_summary }}

    SYNTHESIZED RECORDS JSON:
    {{ synthesized_records_json }}

    {{ ctx.output_format }}
  "#
}
