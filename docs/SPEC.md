# SPEC — devin-graph

A knowledge graph over Devin sessions: sessions, projects (working
directories), files and tools become nodes; `tool_call_state` rows become
`tool_call` nodes with edges recording exactly which call touched which file.
Queryable ("which sessions touched file X?", "which tools does project Y
depend on?") and exportable as D3-friendly JSON.

**Unofficial community project.** Devin's local stores are private internals;
their schema changes without notice (17 migrations so far). This tool depends
on
[`devin-internals-spec`](https://github.com/Icaro0310/devin-internals-spec)
for schema detection and typed parsers instead of guessing SQL.

## 1. Scope

In scope (M1):

- Source: CLI `sessions.db` (schema v15–v17) — `sessions`,
  `tool_call_state`. Read-only, always.
- `extract.py` — session → nodes/edges (see §3).
- `store.py` — persistent `graph.db` (SQLite), incremental re-extract,
  deterministic JSON export.
- `query.py` — canned queries: sessions-for-file, tools-for-project,
  sessions-for-tool, project detail, projects-graph adjacency.
- `cli.py` — `build`, `query file|tool|project|projects-graph`, `export`.

Out of scope:

- GUI sessions (`User/acp-messages/*.db`), `state.vscdb`, `prompt_history`,
  `message_nodes` content (that is `devin-history`'s job).
- Visualization itself — `export`/`projects-graph` emit JSON for D3/other;
  rendering is `devin-dashboard` (M2 queue).
- Writing to Devin stores (never).

## 2. Invariants

1. **Read-only source.** `sessions.db` is opened via
   `devin_internals.parsers.SessionsStore` (`file:...?mode=ro`). Tests assert
   the file hash is unchanged after build/query/export.
2. **Fail loud on schema drift.** Unknown or unsupported schema versions
   raise `SchemaError`; the CLI exits 2 with the detector's message.
3. **Ground truth, not inference.** `file_touched` edges come only from
   `tool_call_state` payloads + `working_directory` — never parsed out of
   prose/messages.
4. **Defensive payloads.** `tool_call_*_json` is *unstable* (SCHEMA.md):
   decoding tolerates NULL/junk/unknown shapes, merges call-over-update, and
   never crashes on a new format.
5. **Deterministic.** No wall-clock values are stored; `export()` output is
   stable for a stable source. Incremental builds key on
   `sessions.last_activity_at`, not file mtimes.

## 3. Graph model

| node kind | key | attrs |
|---|---|---|
| `session` | session id | title, model, created_at, last_activity_at, hidden |
| `project` | normalized `working_directory` | name (basename) |
| `tool_call` | `"{session_id}:{tool_call_id}"` | tool_call_id, session_id |
| `tool` | tool name | — |
| `file` | normalized path | name (basename) |

| edge kind | src → dst |
|---|---|
| `runs_in` | session → project |
| `made_call` | session → tool_call |
| `call_used` | tool_call → tool |
| `tool_used` | session → tool (rollup) |
| `file_touched` | tool_call → file |

Composite ids (`"kind:key"`) are the exported node `id` / edge
`source`/`target`.

### Path extraction (heuristic, documented)

`tool_call_json` has no public schema, so `extract_paths()` walks the decoded
payload and collects:

- string values under path-ish keys (`path`, `file`, `files`, `file_path`,
  `filepath`, `filename`, `abs_path`, `target_file`, …) at any depth — covers
  `rawInput`, `args`, `locations[].path`;
- path-looking tokens inside command-ish keys (`command`, `cmd`, `script`,
  `input`) — either containing a separator or a recognised code/docs
  extension; URLs and flags are skipped.

Tool name: first string among `name`/`tool_name`/`tool`/`kind`/`type`/
`title`, top level or one level inside `rawInput`/`raw_input`/`input`/`args`.

Paths are normalized to `/` separators and relative paths resolve against the
session's `working_directory` (the file touched *is* the one under cwd).

## 4. Storage and incremental build

`graph.db` tables: `nodes(id, kind, key, owner, attrs)`, `edges(kind, src,
dst, owner, attrs)`, `extracted_sessions(session_id, last_activity_at)`,
`meta(key, value)`.

`owner` = the session that produced the row. `session`/`tool_call` nodes and
all edges are owned; `project`/`file`/`tool` nodes are shared (owner NULL).

`GraphStore.build(store)`:

- new or changed (`last_activity_at` differs) session → delete its owned
  rows, re-extract, upsert marker;
- unchanged session → skip;
- session gone from source → delete owned rows + marker;
- finally prune shared nodes left with no incident edges.

## 5. CLI contract

```
devin-graph build [--sessions-db PATH] [--graph PATH] [--json]
devin-graph query file PATH      [--graph PATH] [--json]
devin-graph query tool NAME      [--graph PATH] [--json]
devin-graph query project NAME   [--graph PATH] [--json]
devin-graph query projects-graph [--graph PATH] [--json]
devin-graph export --format json [--graph PATH] [--out FILE]
```

- `--sessions-db` optional; default candidates per platform
  (`%APPDATA%/devin/cli/sessions.db` on Windows, …). Missing → exit 2.
- `--graph` defaults to `./graph.db`; missing graph → exit 2 with a hint.
- `export` prints `{"meta", "nodes", "edges"}` or writes `--out`.
- Matching is forgiving: exact → case-insensitive → suffix
  (`src/app.py` finds `/repo/alpha/src/app.py`).

## 6. Testing

- Fixtures generated at test time via
  `devin_internals.fixtures.create_sessions_db()` + a `conftest` helper that
  plants `tool_call_state` payloads in several plausible shapes (the format
  is unstable — the extractor must not depend on one).
- 57 tests: path normalization, payload tolerance, tool-name priority,
  per-session + whole-store extraction counts, incremental build
  (skip/re-extract/remove/prune), export shape/determinism, every canned
  query, CLI contract incl. failure modes, source DB byte-identical.

## 7. M2 queue

- `devin-dashboard` visualization (consume `export`/`projects-graph` JSON).
- `graphify` interop (emit graphify-compatible nodes).
- Read-only MCP server exposing the canned queries.
- `acp-messages/*.db` (GUI sessions) as a second source.
- PyPI publish.
