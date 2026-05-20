# Commercial Boundary

Lerim core is Apache-2.0. The open-source project should stay useful on its
own: local CLI, local runtime, MCP server, native adapters, SQLite context
store, docs, and benchmark scripts.

The business model is open core, not crippled core.

## Open-Source Core

Keep these in the Apache-2.0 repo:

- CLI and local runtime
- local MCP stdio server
- native trace adapters
- generic trace import and `lerim_trace_submit`
- core context store schema
- local context brief, answer, search, and curation behavior
- benchmark runners and raw result format
- integration docs and examples

The open-source user should be able to install Lerim, connect an agent, ingest
local traces, query context, and reproduce public-data benchmark claims without
a paid account. Internal or private-dataset diagnostics may be published only
as aggregate diagnostic evidence with the private boundary stated clearly.

## Paid Products

Sell operational value around teams, hosted infrastructure, compliance, and
managed workflows:

- Lerim Cloud hosted sync
- hosted private MCP endpoint
- shared team workspaces
- web dashboard and review workflow
- SSO, SAML, SCIM, RBAC, and audit logs
- retention, privacy, and approval controls
- extraction-quality monitoring and evaluation dashboard
- managed support, incident, CRM, and internal-tool integrations
- private deployments and enterprise support

These are valuable because teams need reliability, governance, collaboration,
and low-ops deployment. They do not need the local developer path to be blocked.

## Rules For Product Decisions

- Do not move the basic MCP server behind a paywall.
- Do not move native local adapters behind a paywall.
- Do not require cloud auth for local SQLite context.
- Do not publish benchmark claims that require private paid infrastructure to
  reproduce unless they are clearly labeled cloud-only.
- Paid features should make team operation easier, not make the local core
  artificially worse.

## Launch Wording

Good wording:

> Lerim is Apache-2.0 source-session context compiler infrastructure for AI
> agent workflows, with a hosted team product planned for sync, governance,
> dashboards, and managed integrations.

Avoid:

> The open-source repo is only a demo.

That would undermine the GitHub adoption goal. The core needs to be real.
