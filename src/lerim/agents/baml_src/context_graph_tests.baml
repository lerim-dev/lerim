test LinkContextRecordsKeepsPreciseRelation {
  functions [LinkContextRecords]
  args {
    run_instruction "Build sparse, grounded links between curated context records."
    cluster_id "cluster_approval"
    records_json #"
      [
        {
          "record_id": "rec_policy",
          "kind": "fact",
          "title": "Approval threshold policy",
          "body": "Finance policy requires approval before an agent offers enterprise discounts above the threshold.",
          "status": "active"
        },
        {
          "record_id": "rec_decision",
          "kind": "decision",
          "title": "Require approval for large renewals",
          "body": "Support agents must get approval before promising large renewal discounts.",
          "status": "active"
        }
      ]
    "#
    candidate_pairs_json #"
      [
        {
          "source_record_id": "rec_policy",
          "target_record_id": "rec_decision",
          "shared_signal": "approval required before large discount promises"
        }
      ]
    "#
    existing_edges_json "[]"
  }
  @@assert({{ this.links|length >= 1 }})
  @@assert({{ "related" not in (this.links|map(attribute="relation_kind")|join(" ")) and "RELATED" not in (this.links|map(attribute="relation_kind")|join(" ")) }})
  @@assert({{ "rec_policy" in (this.links|map(attribute="evidence_record_ids")|join(" ")) and "rec_decision" in (this.links|map(attribute="evidence_record_ids")|join(" ")) }})
}

test ReviewContextGraphLinksDropsUngroundedLowConfidenceLink {
  functions [ReviewContextGraphLinks]
  args {
    run_instruction "Keep only useful, grounded context graph links."
    records_json #"
      [
        {
          "record_id": "rec_a",
          "kind": "fact",
          "title": "Billing data refresh",
          "body": "Billing data refreshes nightly.",
          "status": "active"
        },
        {
          "record_id": "rec_b",
          "kind": "constraint",
          "title": "Legal approval needed",
          "body": "Legal approval is needed before changing contract terms.",
          "status": "active"
        }
      ]
    "#
    proposed_links_json #"
      [
        {
          "source_record_id": "rec_a",
          "target_record_id": "rec_b",
          "relation_kind": "related",
          "label": "Maybe related",
          "rationale": "Both mention business operations.",
          "evidence_record_ids": ["rec_a"],
          "confidence": 0.4
        }
      ]
    "#
  }
  @@assert({{ this.links|length == 0 }})
}
