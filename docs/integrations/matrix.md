# Integration Matrix

This page is the public support boundary. An agent is not fully supported until
the relevant recall and capture paths are tested against a real client/config,
not only parser fixtures.

## Launch Summary

| Surface | Current evidence | What works today | Not claimed yet |
| --- | --- | --- | --- |
| Native completed-session adapters | Adapter code and unit/integration fixtures for Claude Code, Codex CLI, Cursor, OpenCode, and pi | Lerim can ingest stable local session stores where the adapter format is current | Every current client version and every OS path |
| MCP config writers | 15/15 config-writer probes in `mcp-integration-full` | `lerim connect <agent> --mode mcp` writes/validates Lerim MCP entries with backups | A live tool call from every external client |
| Installed-client MCP evidence | 3 anonymized connection-visibility acceptances; Gemini CLI live `lerim_context_brief` tool-call artifact | Gemini CLI can call a Lerim context tool through MCP in the current public artifact | Per-client live tool-call acceptance artifacts beyond Gemini |
| Generic trace submission | Local stdio `lerim_trace_submit` duplicate probe and synthetic trace-submit extraction probe | Completed traces can be submitted through CLI import or MCP and processed by Lerim | That every MCP-first agent automatically submits completed sessions |
| Planned deeper capture | OpenClaw plugin, Hermes provider plugin, and pi extension are documented candidates | Current plugin mode reports planned status honestly | Native lifecycle capture for those plugins |

## Native Or Near-Native Sources

| Agent | Current support | Install/config path | Upstream docs | Verified evidence | Not claimed yet |
| --- | --- | --- | --- | --- | --- |
| Claude Code | Native adapter plus MCP config writer | `lerim connect claude-code --mode mcp`; config at `~/.claude.json` | [Claude Code](https://docs.anthropic.com/en/docs/claude-code) | MCP stdio probe plus config-writer evidence | Per-client live tool-call artifact is not available yet; session-end hook not shipped |
| Codex CLI | Native adapter plus MCP config writer | `lerim connect codex --mode mcp`; config at `~/.codex/config.toml` | [Codex](https://developers.openai.com/codex) | MCP stdio probe plus targeted `--run-id` path unit coverage | Public current-client targeted ingest artifact and stable completion hook |
| Cursor | Native adapter plus MCP config writer | `lerim connect cursor --mode mcp`; config at `~/.cursor/mcp.json` | [Cursor MCP](https://docs.cursor.com/tools/mcp) | Config-writer evidence | Current-client DB acceptance artifact |
| OpenCode | Native adapter plus MCP config writer | `lerim connect opencode --mode mcp`; config at `~/.config/opencode/opencode.json` | [OpenCode MCP](https://opencode.ai/docs/mcp-servers/) | MCP stdio probe plus config-writer evidence | Per-client live tool-call artifact is not available yet; current-client capture artifact not available yet |
| pi | Native JSONL session adapter; extension candidate | `lerim connect pi`; source at `~/.pi/agent/sessions/` | See [pi notes](pi.md) | Adapter tests included; not part of MCP config scaffold | MCP config support is not claimed; native extension capture not shipped |

## MCP-First Targets

| Agent | Current support | Install/config path | Upstream docs | Verified evidence | Not claimed yet |
| --- | --- | --- | --- | --- | --- |
| Gemini CLI | MCP config writer | `lerim connect gemini-cli --mode mcp`; config at `~/.gemini/settings.json` | [Gemini CLI MCP](https://github.com/google-gemini/gemini-cli/blob/main/docs/tools/mcp-server.md) | MCP stdio probe and live `lerim_context_brief` artifact | Native completed-session capture |
| Cline VS Code | MCP config writer | `lerim connect cline --mode mcp`; VS Code global storage `cline_mcp_settings.json` | [Cline MCP](https://docs.cline.bot/mcp/configuring-mcp-servers) | Config-writer evidence | Installed-client launch/tool-call artifact |
| Cline CLI | MCP config writer | `lerim connect cline-cli --mode mcp`; config at `~/.cline/mcp.json` | [Cline MCP](https://docs.cline.bot/mcp/configuring-mcp-servers) | Config-writer evidence | Installed-client launch/tool-call artifact |
| Claude Desktop | MCP config writer | `lerim connect claude-desktop --mode mcp`; Claude Desktop config JSON | [MCP user quickstart](https://modelcontextprotocol.io/quickstart/user) | Config-writer evidence | Installed-client launch/tool-call artifact and completed-session capture |
| Goose | MCP config writer | `lerim connect goose --mode mcp`; config at `~/.config/goose/config.yaml` | [Goose](https://block.github.io/goose/) | Config-writer evidence | Installed-client launch/tool-call artifact and session export validation |
| Roo Code | MCP config writer | `lerim connect roo-code --mode mcp`; VS Code global storage `mcp_settings.json` | [Roo Code MCP](https://docs.roocode.com/features/mcp/using-mcp-in-roo) | Config-writer evidence | Installed-client launch/tool-call artifact |
| Kilo Code | MCP config writer | `lerim connect kilo-code --mode mcp`; VS Code global storage `mcp_settings.json` | [Kilo Code MCP](https://kilocode.ai/docs/features/mcp/using-mcp-in-kilo-code) | Config-writer evidence | Installed-client launch/tool-call artifact |
| Windsurf | MCP config writer | `lerim connect windsurf --mode mcp`; config at `~/.codeium/windsurf/mcp_config.json` | [Windsurf MCP](https://docs.windsurf.com/windsurf/cascade/mcp) | Config-writer evidence | Installed-client launch/tool-call artifact and Cascade trace export validation |

## Plugin Candidates And Experimental Paths

| Agent or path | Current support | Install/config path | Upstream docs | Verified evidence | Not claimed yet |
| --- | --- | --- | --- | --- | --- |
| OpenClaw | MCP config writer; plugin candidate | `lerim connect openclaw --mode mcp`; config at `~/.openclaw/openclaw.json` | [OpenClaw MCP](https://docs.openclaw.ai/cli/mcp) | Config-writer evidence for documented nested `mcp.servers` registry | Native plugin capture |
| Hermes | MCP config writer; provider plugin candidate | `lerim connect hermes --mode mcp`; config at `~/.hermes/config.yaml` | [Hermes](https://docs.opencomputer.dev/agents/cores/hermes) | Config-writer evidence | Native provider plugin capture |
| OpenHuman | Experimental generic MCP config writer | `lerim connect openhuman --mode mcp`; config at `~/.openhuman/mcp.json` | [OpenHuman](https://github.com/tinyhumansai/openhuman) | Config-writer evidence only | Client-loading evidence or upstream lifecycle integration |
| Custom trace folder | Supported generic trace folder | `lerim project add <path> --type custom` or `lerim ingest --agent custom` | See [custom traces](../guides/submit-custom-agent-trace.md) | Import path validation | User exporter quality, cleaning, redaction, and retention |
| Generic trace import / MCP submit | Supported generic trace submission | `lerim trace import <path>` or `lerim_trace_submit` | See [MCP quickstart](../guides/mcp-quickstart.md) | MCP trace-submit duplicate and extraction probes | Automatic completed-session submission from every MCP-first agent |

## Evidence Artifacts

| Evidence | Artifact |
| --- | --- |
| Full MCP/config benchmark | `benchmarks/results/raw/mcp-integration-full/report.json`; per-client local inventory is anonymized |
| Gemini CLI live tool-call acceptance | `benchmarks/results/raw/mcp-gemini-live-tool-call/report.json` |
| Per-agent docs | `docs/integrations/<agent>.md` |
| Benchmark boundary | [MCP Integration](../benchmarks/lerim-results.md#mcp-integration) |

## Support Levels

- **Native adapter** means Lerim can read a stable local source-session store.
- **MCP** means Lerim can write or document a client config entry for Lerim's
  MCP tools. Live query or trace-submit acceptance is claimed only when the
  evidence columns list installed-client or tool-call evidence.
- **Plugin/extension planned** means the deeper lifecycle capture path is not
  implemented yet.
- **Recall evidence** and **session capture evidence** separate config-writer
  coverage from installed-client/tool-call validation. Unit fixtures help
  coverage but do not count as final support acceptance.
