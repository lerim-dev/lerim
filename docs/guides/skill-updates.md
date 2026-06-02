# Skill Updates

Lerim can improve the skills and instruction files future agents use.

The flow is:

1. Register a skill or instruction artifact.
2. Refresh it from scoped Lerim context records.
3. Review generated proposals in the dashboard.
4. Inspect the diff and full-file preview.
5. Apply or reject the proposal.
6. Optionally enable auto-apply for trusted targets.

This is separate from installing Lerim's own agent skill. `lerim skill install`
installs the Lerim startup skill so agents can query context. Skill updates
register other skill or instruction files that Lerim may monitor and improve.

## Register A Target

Register any skill or instruction artifact Lerim should monitor:

```bash
lerim skill target add ~/.agents/skills/clean-code \
  --description "Keep simplification guidance current"
lerim skill target list
lerim skill target show it_abc123
```

Supported targets include skill directories, `SKILL.md`, `AGENTS.md`,
`CLAUDE.md`, `GEMINI.md`, and related instruction files.

Targets inside a registered Lerim project are scoped to that project. Targets
outside registered projects are global and may learn from records across
registered projects.

## Generate Proposals

Run a refresh to scan relevant context records and compile proposed updates:

```bash
lerim skill refresh clean-code
lerim skill refresh clean-code --record-limit 120 --json
```

The proposal pipeline uses durable records from past traces, chats, decisions,
failed paths, and user preferences. Every patch must cite source record ids, so
reviewers can connect the edit back to learned evidence.

## Review In The Dashboard

Open the dashboard:

```bash
lerim dashboard
```

Then open the Skills tab.

The Skills tab shows:

- registered skill and instruction targets
- update mode and auto-apply policy
- pending and applied proposals
- proposal guard and validation status
- unified diff preview with line numbers
- full-file preview with line numbers
- apply and reject actions

The normal review flow is intentionally similar to an IDE or coding-agent patch
review: Lerim proposes a change, shows the diff, and waits for confirmation.

## Apply Or Reject

Applying a proposal writes the original target file on disk. Lerim allows that
only when the proposal is pending, validation passed, the guard accepted it, and
the current file still matches the baseline captured when the proposal was
created.

Rejecting a proposal marks it terminal and leaves the file unchanged.

Use the CLI when you want to inspect or apply from a terminal:

```bash
lerim skill proposal list
lerim skill proposal list --target-id it_abc123 --status pending_review
lerim skill proposal show ip_abc123
lerim skill proposal apply ip_abc123
lerim skill proposal reject ip_abc123
```

## Enable Auto-Apply

Targets default to review mode. Enable auto-apply only for targets you trust:

```bash
lerim skill target auto-apply it_abc123 --enable --risk low
lerim skill target auto-apply it_abc123 --disable
```

Auto-apply remains bounded by policy. The default policy checks validation,
evidence, risk, changed-file count, added lines, removed lines, and allowed
surfaces before writing files.

Scripts, assets, config files, and frontmatter stay blocked unless the target
policy explicitly allows them.

## Safety Model

Skill updates are designed to be reviewable and bounded:

- Proposal paths are limited to files scanned as part of the registered target.
- Skill bundles may propose new files only under `references/`, `reference/`,
  or `examples/`.
- Patches must include evidence record ids.
- Applying checks that file contents still match the proposal baseline.
- Applied, rejected, and superseded proposals cannot be edited back into review.
- Auto-apply is opt-in per target.

For command details, see [CLI: lerim skill](../cli/skill.md). For the dashboard
surface, see [Dashboard](dashboard.md).
