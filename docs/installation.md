# Installation

Install Lerim, connect your agent traces, and start the service.

## Install

```bash
pip install lerim
```

## Initialize

```bash
lerim init
```

This writes user config to `~/.lerim/config.toml`.

## Connect agents

```bash
lerim connect auto
```

Or connect one platform manually:

```bash
lerim connect claude
lerim connect codex
```

## Register a project

```bash
lerim project add .
```

This only registers the repo path.
It does not create a durable local `.lerim` store.

## Start Lerim

```bash
lerim up
```

Or run the server directly:

```bash
lerim serve
```
