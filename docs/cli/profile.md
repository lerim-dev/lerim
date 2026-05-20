# lerim profile

Inspect bundled source profiles and register custom YAML profiles.

Source profiles guide extraction. They tell Lerim what durable signal, noise,
evidence, and scope boundaries matter for a workflow. They do not create a new
record schema or a separate memory store.

## Syntax

```bash
lerim profile list
lerim profile show <profile>
lerim profile validate <profile.yaml>
lerim profile register <profile.yaml> [--force]
```

## Commands

| Command | Use it for |
| --- | --- |
| `list` | Show bundled and registered source profiles with record counts. |
| `show <profile>` | Show profile rules plus recent stored records for that profile. |
| `validate <profile.yaml>` | Check a custom YAML profile without changing config. |
| `register <profile.yaml>` | Add a valid custom profile to `[profiles]` in the active config. |

## Examples

```bash
lerim profile list
lerim profile show support
lerim profile validate ./research.yaml
lerim profile register ./research.yaml
```

After registration, use the profile id anywhere Lerim accepts
`--source-profile`:

```bash
lerim trace import ./research-run.jsonl \
  --source-name research-agent \
  --source-profile research \
  --scope-type domain \
  --scope research
```

For ongoing custom trace folders, register the folder with a default profile:

```bash
lerim project add ~/lerim-traces/research-clean \
  --type custom \
  --source-profile research
```

See [Customize Lerim For Your Use Case](../guides/custom-source-profiles.md)
for the YAML fields and full workflow.
