# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `shared_files` query + `devin-graph query shared-files`: lists files
  touched by two or more distinct projects, with the project and
  session lists; text and `--json` output like the other queries.

### Changed

- `llms.txt` no longer states a hard-coded ecosystem size; the registry owns the count.

## [0.1.0] - 2026-09-29

### Added

- `extract.py` — knowledge-graph extraction from `sessions.db`: `session`,
  `project`, `file`, `tool` and `tool_call` nodes with `runs_in`,
  `made_call`, `call_used`, `tool_used` and `file_touched` edges. File paths
  are mined defensively from `tool_call_state` payloads and resolved against
  the session's working directory.
- `store.py` — `GraphStore`: persistent SQLite `graph.db` with incremental
  re-extract (per-session `last_activity_at` markers), orphan pruning and a
  deterministic JSON export (`{meta, nodes, edges}`).
- `query.py` — canned queries: sessions-for-file, sessions-for-tool,
  tools-for-project, project detail and projects-graph adjacency JSON.
- `cli.py` — `devin-graph build`, `devin-graph query
  file|tool|project|projects-graph` and `devin-graph export --format json`,
  all with `--json` / `--graph` / `--sessions-db` plumbing; read-only on
  Devin stores.
- `paths.py` — platform-aware default `sessions.db` discovery.
- `docs/SPEC.md` — graph model, invariants, storage and CLI contract.
- Test suite (57 tests) on generated fixtures — real v17 DDL, synthetic
  `tool_call_state` payloads in multiple shapes.
