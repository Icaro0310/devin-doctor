# devin-explore

<!-- DEVIN-ECO:BEGIN -->
> **Part of the [DEVIN ecosystem](https://github.com/Icaro0310/awesome-devin)**  
> Track: Understand · Nature: product  
> For: Operations, End users  
> Interface: CLI  
> Path: End users · step 3/3 — after `devin-devkit`  
> Path: Operations · step 1/4 — before `devin-backup`
<!-- DEVIN-ECO:END -->

Understand your Devin sessions: diagnose the local installation, export
and search session history, and query a knowledge graph of projects,
files, tools and decisions — all local, no telemetry.

| Package | PyPI | What it does |
|---|---|---|
| [`packages/doctor`](packages/doctor) | `devin-doctor` | Diagnose a Devin Desktop install: stores, schema versions, hooks, MCP servers, disk usage |
| [`packages/history`](packages/history) | `devin-history` | Export, audit and search session history — Obsidian-ready markdown, JSON, SQLite-aware |
| [`packages/search`](packages/search) | `devin-search` | Full-text search across all Devin sessions |
| [`packages/graph`](packages/graph) | `devin-graph` | Knowledge graph over sessions: projects, files, tools, decisions as nodes |
| [`packages/pm`](packages/pm) | `devin-pm` | Turn session history into milestones, status reports and per-repo task tracking |

> **Renamed (Oct 2026):** this repository moved from `Icaro0310/devin-doctor` to `Icaro0310/devin-explore` when it became the `devin-explore` product workspace. PyPI packages and console scripts keep their names; stars, issues and history are preserved by the redirect.

## Layout

```
packages/<name>/   one installable package each (src layout, own tests)
```

Each package ships independently: a tag `<pkg>-vX.Y.Z` publishes only
that package. CI is scoped per path — a change under `packages/graph/`
runs only the graph suite.

The standalone `devin-history`, `devin-search`, `devin-graph` and
`devin-pm` repositories were absorbed into this workspace (F4.3); their
histories are preserved under `packages/` and the old repos are archived
with pointers here.

## Platform support

All packages support Linux, macOS and Windows. Per-package guides live
under `packages/<name>/`.

> **Unofficial community project.** Not affiliated with, endorsed by, or
> sponsored by Cognition AI. "Devin" is a trademark of Cognition AI.
