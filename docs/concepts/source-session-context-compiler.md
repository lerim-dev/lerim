# Source-Session Context Compiler

Lerim's central idea is simple: the best durable memory often comes after an
agent run is complete.

A source session is one completed workflow: a coding-agent run, support triage,
incident investigation, research pass, sales workflow, or internal automation.
It has inputs, intermediate work, tool evidence, user corrections, decisions,
failed paths, and final outcomes.

Lerim compiles that source session into context records future agents can trust.

## Why Completed Sessions Matter

Live turns are noisy. They contain retries, tool chatter, partial thoughts,
wrong paths, duplicated status updates, and transient payloads.

After the run finishes, Lerim can ask better questions:

- What did the agent actually learn?
- Which constraints should future agents preserve?
- Which decision was made, and what evidence supports it?
- Which failed path should not be repeated?
- Which handoff or open question still matters?
- Which routine details should be archived instead of becoming durable memory?

That is why Lerim's main primitive is not `memory_save`. The compiler looks at
the whole source session and decides what is reusable.

## Compiler Stages

| Stage | Job | Output |
| --- | --- | --- |
| Capture | Read or receive a completed source session. | Raw or normalized session event stream. |
| Normalize | Convert source-specific traces into Lerim's compact event shape. | Canonical user/assistant trace. |
| Extract | Use the source profile to find durable signal. | Candidate records with source evidence. |
| Store | Write accepted records into the context store. | Project, domain, workspace, user, session, or custom scoped records. |
| Curate | Merge overlap, archive weak records, and link related records. | Compact context graph and healthier durable context. |
| Serve | Answer questions and compile startup context. | Cited answers and `lerim_context_brief` output. |

## What Counts As Durable Context

Good durable context is useful outside the original trace:

- decisions and rationale
- preferences and operating rules
- constraints and policies
- reusable facts
- evidence links and source references
- handoffs and unresolved questions
- failed approaches that future agents should avoid
- setup, environment, or workflow lessons

Routine progress updates, duplicate logs, raw tool payloads, screenshots,
secrets, and temporary chatter should not become durable records.

## Source Profiles

Different workflows produce different signal.

| Profile | Signal to keep |
| --- | --- |
| Coding | Architecture decisions, repo conventions, failed commands, setup facts, test lessons, release handoffs. |
| Support | Customer constraints, escalation reasons, known fixes, failed fixes, policy-backed facts, handoffs. |
| Ops/incidents | Root causes, mitigations, rejected hypotheses, owner decisions, runbook gaps, follow-up risks. |
| Custom | Customer-defined workflow signal from clean JSONL traces. |

The compiler stays shared. Profiles change what signal matters, not the storage
architecture.

## Evidence Boundary

Every important record should point back to the source session. A future agent
should be able to ask why a record exists and inspect the supporting trace.

This evidence boundary is what makes Lerim different from a loose memory bucket.
It also makes benchmark and review workflows possible: records can be checked
against their source instead of treated as free-floating claims.

## How Agents Use The Result

Future agents can access compiled context through:

- `lerim answer` for grounded questions
- `lerim context-brief` for startup context
- `lerim mcp` tools such as `lerim_context_brief`,
  `lerim_context_answer`, and `lerim_context_search`
- native product workflows that read the same context store

The agent receives compact, cited operating context instead of the entire raw
history.
