# STATUS — devin-graph

Updated: 2026-09-29 · Milestone: **M1 (done)** · Version: 0.1.0

## Done in M1

- `src/devin_graph/`:
  - `extract.py` — nodes `session` / `project` / `file` / `tool` /
    `tool_call`; edges `runs_in`, `made_call`, `call_used`, `tool_used`,
    `file_touched`. Paths pulled defensively from `tool_call_*_json`
    (path-keys at any depth + path tokens in command strings), normalized to
    `/` and resolved against `working_directory`; call payload wins over
    update payload.
  - `store.py` — `GraphStore` on local SQLite `graph.db`
    (`nodes`/`edges`/`extracted_sessions`/`meta`); incremental re-extract
    keyed on `last_activity_at`, deletes gone sessions, prunes orphaned
    shared nodes; deterministic `export()` (`{meta, nodes, edges}`).
  - `query.py` — sessions-for-file, sessions-for-tool, tools-for-project,
    project detail, projects-graph adjacency (`{nodes, links}` for D3).
  - `cli.py` — thin argparse: `build`, `query file|tool|project|
    projects-graph`, `export --format json [--out]`; `--json` everywhere;
    exit 2 on store/graph errors.
  - `paths.py` — default `sessions.db` candidates per platform.
- `docs/SPEC.md` (EN), real READMEs (EN/PT-BR).
- **57 tests, all green** (Windows, Python 3.11.9, pytest 9.1.1) — fixtures
  generated at test time via `devin_internals.fixtures` + a conftest helper
  planting `tool_call_state` payloads in several shapes.
- Verified on fixture DB: `build` → `query` → `export` end-to-end;
  incremental rebuild skips unchanged sessions; source DB byte-identical.

## Environment notes

- `python` = 3.11.9 w/ pytest; bare `pip` → Python 3.14. Always
  `python -m pip`.
- `pip install -e .` hangs resolving the git dep URL from this network —
  use `--no-deps` (dep already installed).
- `/tmp` in the shell ≠ `/tmp` for Windows Python — pass Windows-style paths
  (`C:/tmp/...`) to CLI verification commands.

## Decisions / notes

- `tool_call` kept as a node kind (not just an edge attribute) — it is the
  ground-truth differentiator and makes "which call touched X" answerable.
- `owner` column on nodes/edges = producing session; shared nodes
  (project/file/tool) have NULL owner and are pruned when edgeless.
- Command-string path mining is intentionally conservative (separator or
  known extension required; URLs/flags skipped) — documented as heuristic in
  SPEC §3.
- Matching (file/tool/project queries): exact → case-insensitive → suffix.

## M2 queue (per KICKOFF-M1)

1. `devin-dashboard` viz integration (consume export / projects-graph JSON).
2. `graphify` interop.
3. Read-only MCP server exposing the canned queries.
4. `acp-messages/*.db` (GUI sessions) as a second source.
5. PyPI publish.

## Blockers

None.
