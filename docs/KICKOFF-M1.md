# KICKOFF M1 — devin-search

Dedicated session for THIS repo. Template scaffold — fill with real
content. `docs/SPEC.md` EN, shared README plus Windows/Linux guides
(problem/prior art/Devin extra/limitations/install), logic in `src/devin_search/` + thin `cli.py`,
small commits + Devin trailer, push, STATUS.md + CHANGELOG.md.

## One sentence

Full-text search over every Devin session — find a command, an error
message, a file path or a decision across months of history in <1s.

## Devin-native differentiator

Indexes Devin's real message structure (user/assistant/tool-call roles via
devin-internals parsers) so results are role-tagged and link back to the
exact session — not generic grep over logs.

Dep: `"devin-internals-spec @ git+https://github.com/Icaro0310/devin-internals-spec.git@v0.2.0"`

## Scope (M1)

`src/devin_search/`:
- `index.py` — build a local SQLite FTS5 index (`search.db`) from
  sessions.db + acp-messages; incremental (re-index only new rows);
  fields: session_id, role, ts, cwd/project, snippet, rowid ref.
- `query.py` — `search <term>` → ranked hits (BM25 via FTS5) with role +
  project + session link; filters `--role`, `--project`, `--since`.
- `fmt.py` — terminal table or `--json`.

## CLI

- `devin-search index [--sessions-db <db>] [--acp-dir <dir>] [--index <path>]`
- `devin-search query "<term>" [--role user] [--project x] [--limit N] [--json]`
- Read-only on Devin stores; index file is the only write.

## Fixtures/tests

`devin_internals.fixtures` stores with searchable content; tests: index
build + incremental, FTS ranking, filters, JSON shape, source stores
unchanged (hash compare).

## Env notes

`python`=3.11.9; `python -m pip` only; no multi-line `python -c`; Windows.

## Done

Tests green · CLI verified on fixture · docs real · pushed. M2 queue in
STATUS.md: TUI/browser results, Obsidian link output, semantic search
opt-in, PyPI.
