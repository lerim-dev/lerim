# Lerim

Lerim is a context compiler. It compiles completed agent traces into cited, reusable context.

_Lerim is an independent open-source project by [Nablo](https://nablo.io). It is not part of the Nablo pipeline and does not train models._

It filters noisy execution history into evidence-backed context records:
decisions, preferences, constraints, facts, references, and compact episode
history.

## Summary

Lerim sits after trace systems and before future agents. Observability shows
what happened; Lerim decides what was worth learning from it.

The strongest native capture path today is coding agents. Support operations
and operations/incidents have documented custom-trace paths and source profiles,
not separate pipelines.

If you are evaluating Lerim, start with the workflow: traces in, durable context
out, cited answers and startup context for future agents.

Public support and benchmark claims are intentionally artifact-backed. The
integration matrix separates config support from native trace capture, and the
benchmark pages name the raw `report.json` evidence behind each number.

The operating model is simple:

- capture traces from supported agent work
- expose context to MCP-compatible agents
- filter noisy execution history into durable signal
- curate overlap so context stays compact
- link related context into a navigable graph
- answer questions and compile startup context for future agents
- propose updates to registered agent skills and instruction files

## Main phases

- `ingest` extracts durable records from supported traces
- `curate` merges and archives low-value records so memory stays selective
- `context_graph` links curated records into a sparse context graph during curate cycles
- `answer` retrieves records and answers a question
- `skill` registers instruction targets and manages evidence-backed update proposals

## Focused workflows

- Coding agents preserve repo conventions, architecture decisions, setup facts, failed commands, test lessons, and release handoffs.
- Support operations preserve customer constraints, known fixes, failed fixes, escalation reasons, policy-backed facts, and handoffs.
- Operations and incidents preserve root causes, mitigations, rejected hypotheses, runbook gaps, incident handoffs, and follow-up risks.

## Start here

- [Installation](installation.md)
- [Quickstart](quickstart.md)
- [Source-Session Context Compiler](concepts/source-session-context-compiler.md)
- [Integration Matrix](integrations/matrix.md)
- [Benchmarks](benchmarks/index.md)
- [Business Workflows](concepts/business-workflows.md)
- [Custom Trace Folders](guides/custom-trace-folders.md)
- [Submit A Custom Agent Trace](guides/submit-custom-agent-trace.md)
- [Skill Updates](guides/skill-updates.md)
- [Examples](examples/index.md)
- [MCP Quickstart](guides/mcp-quickstart.md)
- [CLI Overview](cli/overview.md)
