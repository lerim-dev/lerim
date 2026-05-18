"""Shared card-type semantics for source-profile signal packs."""

from __future__ import annotations

CARD_KIND_DEFAULTS = {
    "architecture_decision": "decision",
    "constraint": "constraint",
    "customer_constraint": "constraint",
    "decision": "decision",
    "escalation": "constraint",
    "failed_path": "fact",
    "follow_up_risk": "fact",
    "guardrail_candidate": "fact",
    "handoff": "constraint",
    "known_fix": "fact",
    "mitigation": "fact",
    "owner_decision": "fact",
    "policy_reference": "reference",
    "product_behavior": "fact",
    "rejected_hypothesis": "fact",
    "release_handoff": "constraint",
    "repeated_waste": "fact",
    "repo_convention": "constraint",
    "root_cause": "fact",
    "runbook_gap": "fact",
    "setup_fact": "fact",
    "source_of_truth": "reference",
    "test_lesson": "fact",
}

WORKFLOW_CARD_TYPES = {
    "escalation",
    "failed_path",
    "follow_up_risk",
    "handoff",
    "mitigation",
    "owner_decision",
    "rejected_hypothesis",
    "release_handoff",
    "repeated_waste",
    "root_cause",
    "runbook_gap",
}

REFERENCE_CARD_TYPES = {"policy_reference", "source_of_truth"}
