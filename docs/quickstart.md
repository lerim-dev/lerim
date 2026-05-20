# Quickstart

This is the shortest working path.

The open-source quickstart uses the sources available in the current package.
Customer deployments can register custom clean-trace folders around a specific
business workflow such as support escalations, research briefs, incidents,
reviews, or revenue handoffs.

## 1. Prepare

```bash
pip install lerim
lerim init
lerim connect auto
lerim connect auto --mode mcp --dry-run
lerim connect auto --mode mcp
lerim project add .
```

## 2. Start the service

```bash
lerim up
```

## 3. Check status

```bash
lerim status
lerim status --live
```

## 4. Run the flows

Use native adapters when you already have completed sessions from supported
local agents:

```bash
lerim ingest
lerim curate
lerim answer "What sources supported our last competitor-pricing assumption?"
```

For a reproducible first import without depending on an existing agent trace,
create a tiny clean JSON trace and import it:

```bash
cat > /tmp/lerim-demo-trace.json <<'JSON'
{
  "session_id": "quickstart-demo",
  "messages": [
    {
      "role": "user",
      "content": "Standing support rule: before promising a refund, verify entitlement and latest invoice evidence."
    },
    {
      "role": "assistant",
      "content": "I will keep that as a support-operations prerequisite before refund promises."
    }
  ]
}
JSON

lerim trace import /tmp/lerim-demo-trace.json \
  --source-name quickstart-demo \
  --source-profile support \
  --scope-type domain \
  --scope support-demo
```

## 5. Know where data lives

Global Lerim state includes:

- the durable context store
- the session catalog and work queue
- workspace artifacts for ingest, curate, answers, and context briefs
