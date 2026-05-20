# MCP vs Native Adapters

Lerim supports agents through two different integration layers. They should not
be marketed as the same thing.

## The Difference

| Layer | What it does | Best for | What it does not prove |
| --- | --- | --- | --- |
| Native adapter | Reads completed local sessions from a known source and feeds Lerim's compiler. | Reliable capture from agents with stable local trace stores. | It does not mean the agent can query Lerim during a live run. |
| MCP server | Lets compatible agents query Lerim context and submit completed traces. | Broad recall support across many clients. | It does not automatically capture every completed session. |
| Native plugin or hook | Uses an agent's lifecycle hooks to prefetch context or submit a completed run. | Deeper integration when the agent exposes stable extension points. | It should not be claimed until the hook path is implemented and tested. |
| Custom trace import | Lets teams submit clean JSON/JSONL/text traces. | Internal agents and business workflows without built-in adapters. | The customer still owns export, cleaning, redaction, and retention. |

## When MCP Is Enough

MCP is enough when the goal is context access:

- "What should I know before working in this repo?"
- "Search prior context for this customer."
- "List relevant constraints for this incident."
- "Submit this completed transcript through `lerim_trace_submit`."

MCP is also the fastest way to support many agents because the generated client
config starts the installed Python environment with `-m lerim.mcp_server` and
talks to a stable tool surface. The `lerim mcp` CLI command is still available
for local manual runs.

## When Native Capture Is Needed

Native capture is needed when Lerim should automatically learn from completed
agent sessions without asking the user to paste or submit a transcript.

That requires a stable source of completed sessions:

- local JSONL session logs
- local SQLite session stores
- agent lifecycle hooks
- extension APIs
- reliable export commands

If an agent does not expose one of those, Lerim should call it MCP recall or
manual/custom submission, not native support.

## Support Claim Rules

Use these labels in docs, README, and launch copy:

| Label | Meaning |
| --- | --- |
| Native trace ingestion | Lerim has an adapter that reads completed sessions from that source. |
| MCP config support | `lerim connect <agent> --mode mcp` can write and verify the client config. |
| MCP connection verified | The installed client can see or connect to the Lerim MCP server. |
| MCP tool call verified | The installed client has actually called a Lerim MCP context tool. |
| Plugin planned | A native extension could add deeper lifecycle capture, but it is not shipped. |
| Investigating | A possible path exists, but no support claim should be made. |

Fixtures and parser tests are useful engineering coverage. They do not count as
installed-client support acceptance.

## Decision Flow

1. If the agent has a stable local trace store, build or keep a native adapter.
2. If the agent supports MCP, add MCP config support.
3. If the agent has lifecycle hooks, consider a plugin only when it adds
   automatic capture or startup injection beyond MCP.
4. If no stable integration exists, document custom trace submission.
5. Mark the public support state based on the strongest implemented, tested path.

## Current Lerim Boundary

Native adapters exist for Claude Code, Codex CLI, Cursor, OpenCode, and pi.

MCP config support exists for the broader agent set listed in the integration
matrix. Some installed-client connection probes have been verified, but live
tool-call probes are opt-in because they can use paid model subscriptions.

OpenClaw and Hermes are plugin candidates. pi already has native JSONL session
ingestion, while the deeper pi extension path should stay "planned" until it is
implemented and tested.
