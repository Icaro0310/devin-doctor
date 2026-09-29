# KICKOFF M1 — devin-graph

Dedicated session for THIS repo. Template scaffold — fill with real
content. `docs/SPEC.md` EN, bilingual READMEs, logic in
`src/devin_graph/` + thin `cli.py`, small commits + Devin trailer, push,
STATUS.md + CHANGELOG.md.

## One sentence

A knowledge graph over Devin sessions: projects, sessions, files touched,
tools used and repos become nodes with edges — queryable ("which sessions
touched file X?", "which tools does project Y depend on?").

## Devin-native differentiator

Edges extracted from `tool_call_state` (file paths in terminal/fs tool
calls) + `working_directory` — ground truth of what the agent touched,
not inferred from prose.

Dep: `"devin-internals-spec @ git+https://github.com/Icaro0310/devin-internals-spec.git@v0.2.0"`

## Scope (M1)

`src/devin_graph/`:
- `extract.py` — nodes: session, project(cwd), file(path), tool(name);
  edges: session→project, session→tool_used, tool_call→file_touched.
- `store.py` — persist to a local SQLite `graph.db` (nodes/edges tables)
  or `graph.json` export; incremental re-extract.
- `query.py` — canned queries: sessions-for-file, tools-for-project,
  projects-graph (adjacency JSON for visualization).

## CLI

- `devin-graph build [--sessions-db <db>] [--graph <path>]`
- `devin-graph query file "<path>" | tool "<name>" | project "<name>" [--json]`
- `devin-graph export --format json` (nodes+edges for D3/other)
- Read-only on Devin stores.

## Fixtures/tests

Fixtures with tool_call_state containing file paths; tests: node/edge
extraction, incremental build, each canned query, export JSON valid,
stores untouched.

## Env notes

`python`=3.11.9; `python -m pip` only; no multi-line `python -c`; Windows.

## Done

Tests green · CLI verified on fixture · docs real · pushed. M2 queue in
STATUS.md: `devin-dashboard` viz integration, graphify interop, MCP
server, PyPI.
