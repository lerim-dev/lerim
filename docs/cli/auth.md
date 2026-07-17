# lerim auth

Authenticate the local CLI with a self-hosted Lerim sync server.

## Examples

```bash
lerim auth
lerim auth --token <token>
lerim auth status
lerim auth logout
```

## Notes

- Auth stores the cloud token in the active Lerim config.
- Local ingest, curate, and answer do not require self-hosted Lerim sync auth.
