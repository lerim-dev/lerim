# lerim project

Register or remove project paths.

## Summary

Projects are path registrations.
They are not storage roots.

## Examples

```bash
lerim project add .
lerim project add ~/codes/my-app
lerim project add ~/lerim-traces/support-clean \
  --type custom \
  --source-profile support
lerim project list
lerim project remove my-app
```

## Source type

`lerim project add` defaults to `--type supported`.

Use `--type supported` for normal projects whose sessions come from connected
Claude Code, Codex CLI, Cursor, OpenCode, or pi adapters.

Use `--type custom` for folders of already-clean Lerim canonical JSONL traces.
Custom projects are read directly. Lerim does not compact, rewrite, normalize,
or clean files in custom folders.

Use `--source-profile <id>` when a custom trace folder should always extract
through one bundled or registered source profile. To create a new profile, see
[Customize Lerim For Your Use Case](../guides/custom-source-profiles.md).

## How it works

Lerim stores the project path in user config.
Durable context still lives in the global database.
