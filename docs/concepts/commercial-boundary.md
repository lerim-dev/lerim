# Commercial Boundary

Lerim core is Apache-2.0 and should stay useful on its own: local CLI, local
runtime, MCP server, native adapters, SQLite context store, docs, and benchmark
scripts.

The business model is open core, not crippled core.

## Open-Source Core

The Apache-2.0 repo should let a user install Lerim, connect an agent, ingest
local traces, query context, and reproduce public-data benchmark claims without
a paid account. Internal or private-dataset diagnostics may be published only
as aggregate diagnostic evidence with the private boundary stated clearly.

Keep these in the open-source core:

- CLI and local runtime
- local MCP stdio server
- native trace adapters
- generic trace import and `lerim_trace_submit`
- core context store schema
- local context brief, answer, search, and curation behavior
- benchmark runners and raw result format
- integration docs and examples

## Hosted And Team Products

Paid products should sell operational value around teams, hosted
infrastructure, compliance, and managed workflows:

- hosted sync and private MCP endpoints
- shared team workspaces
- web dashboard and review workflow
- SSO, SAML, SCIM, RBAC, and audit logs
- retention, privacy, and approval controls
- extraction-quality monitoring and evaluation dashboards
- managed support, incident, CRM, and internal-tool integrations
- private deployments and enterprise support

The local open-source path should not be artificially weakened to create a paid
upgrade.
