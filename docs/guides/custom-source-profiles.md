# Customize Lerim For Your Use Case

Use a custom source profile when your agent workflow has different durable
signals than the bundled `coding`, `generic`, `support`, or `ops` profiles.

Examples:

- research agents that should remember source-quality rules, preferred
  evidence, and recurring analyst assumptions
- sales agents that should remember approval boundaries, customer-safe claims,
  and handoff rules
- personal assistants that should remember stable preferences and ignore
  one-off scheduling chatter
- internal business agents that produce clean completed traces for a specific
  vertical

The profile is extraction guidance. It tells Lerim what to notice and what to
discard while preserving the same context-record model.

## 1. Write A Profile YAML

Create a YAML file with one profile id and four rule groups:

```yaml
id: research
display_name: Research Analyst
description: Research and market-analysis agent traces.

focus_rules:
  - durable analyst preferences and source-quality rules
  - recurring assumptions that should guide future research runs
  - source-backed conclusions that apply beyond one report

reject_as_noise:
  - temporary browsing failures
  - dead links without a reusable lesson
  - raw quotes that do not support a durable conclusion

evidence_rules:
  - keep source URLs, dates, and uncertainty qualifiers
  - distinguish confirmed facts from hypotheses
  - preserve source caveats instead of turning them into certainty

scope_rules:
  - use domain scope for reusable research workflow context
  - use project scope only when the context is tied to one repository
```

Field rules:

| Field | Required | Meaning |
| --- | --- | --- |
| `id` | Yes | Lowercase profile id. Use letters, numbers, `-`, or `_`. |
| `display_name` | Yes | Human-readable name shown by `lerim profile list/show`. |
| `description` | Yes | One-sentence workflow description. |
| `focus_rules` | Yes | What Lerim should treat as likely durable signal. |
| `reject_as_noise` | Yes | What Lerim should avoid storing as reusable context. |
| `evidence_rules` | Yes | What evidence, caveats, and provenance should survive extraction. |
| `scope_rules` | Yes | Which scope boundaries fit this workflow. |

Do not add output schemas, keyword lists, or one-off phrases. A profile should
describe the workflow boundary, not memorize examples from one trace.

## 2. Validate And Register It

```bash
lerim profile validate ./research.yaml
lerim profile register ./research.yaml
```

Registration writes the profile path into the active config:

```toml
[profiles]
research = "/absolute/path/to/research.yaml"
```

Use `--force` only when you intentionally replace an existing registration for
the same profile id.

## 3. Use It During Extraction

For one file:

```bash
lerim trace import ./research-run.jsonl \
  --source-name research-agent \
  --source-profile research \
  --scope-type domain \
  --scope research
```

For an MCP-capable agent, pass the same id in `lerim_trace_submit`:

```json
{
  "source_name": "research-agent",
  "source_profile": "research",
  "scope_type": "domain",
  "scope": "research",
  "trace_text": "{\"messages\":[{\"role\":\"user\",\"content\":\"Summarize the filings.\"}]}"
}
```

For an ongoing clean-trace folder:

```bash
lerim project add ~/lerim-traces/research-clean \
  --type custom \
  --source-profile research

lerim ingest --agent custom
```

The project registration stores:

```toml
[project_profiles]
research-clean = "research"
```

That makes background ingest use the profile automatically for sessions from
that folder.

## 4. Verify The Result

```bash
lerim profile list
lerim profile show research
lerim context records --profile research
lerim answer "What should the research agent remember?"
```

If no records appear, inspect the trace first. Lerim is selective by design:
routine sessions can produce zero durable records.

## Connecting Traces And Agents

Use the existing connection guides instead of duplicating setup:

- Native or MCP client setup: [Connecting Agents](connecting-agents.md)
- One-off trace files and MCP submission: [Submit A Custom Agent Trace](submit-custom-agent-trace.md)
- Ongoing clean-trace folders: [Custom Trace Folders](custom-trace-folders.md)
- MCP setup details: [MCP Quickstart](mcp-quickstart.md)
- Support status by agent: [Integration Matrix](../integrations/matrix.md)
