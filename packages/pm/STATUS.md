# STATUS — devin-pm

Updated: 2026-10-05 · Milestone: **M1 (done)** · Version: 0.1.0

## Post-M1 updates

- `src/devin_pm/vscdb.py` + `--vscdb [PATH]` flag on every subcommand
  (PM-1): GUI session→workspace bindings from `state.vscdb`
  (`windsurfSpace.sessionWorkspace/<backend>/<slug>` → `{workspaceId,
  label, folders[], lastUpdated}`) merge into the same grouping as
  `sessions.db`. `GuiSession` is Session-shaped (`status`/`source` =
  `gui`); bare flag auto-detects `<config>/Devin/User/globalStorage/
  state.vscdb` (`DEVIN_PM_STATE_VSCDB` override), missing store warns and
  continues CLI-only, explicit missing PATH exits 2. Output marks gui
  sessions: `GUI` column in `status`, `source` column in reports,
  `gui_sessions` in JSON/registry. Read-only via `StateVscdbStore`.
- `src/devin_pm/paths.py` — `normalize_path()` grouping key (PM-3):
  `C:\x` ⇄ `/c/x` ⇄ `/cygdrive/c/x` (+ full case-fold on drive-rooted
  paths), `\\wsl.localhost\<distro>\…`/`\\wsl$\…` → in-distro POSIX,
  separator collapse. Grouping key only; originals kept in output; POSIX
  case preserved. PM-1+PM-3: 25 tests (`test_vscdb.py`, `test_paths.py`),
  all green.
- `src/devin_pm/verify.py` + `verify` subcommand (PM-2): cross-checks
  pm-tracked projects against `devin-powerups/registry.json`
  (`--registry`, default `../devin-powerups/registry.json` from cwd, then
  this package's sibling checkout). Reports registry entries unknown to
  pm (informational), pm-tracked projects missing from the registry
  (drift only when ecosystem-shaped — `devin-*` name or under the hub's
  parent dir), and `name`/`description`/`url` field drift read from the
  checkout's `pyproject.toml` + git `origin`. `--pm-registry` verifies a
  saved export; `--json` supported. Exit 1 on drift, 0 when clean.
  Foreign-platform `working_directory` values (e.g. `C:/...` rows on
  Linux) never count as path-relevant. 25 tests, all green.

## Done in M1

- `src/devin_pm/projects.py` — `group_sessions()` → `Project` model:
  name = working-directory basename, session count/ids, last activity,
  `status_counts` (`active`/`hidden`), best-effort `cost` from `cogs_json`.
  `default_sessions_db()` auto-detect (`DEVIN_PM_SESSIONS_DB` → platform
  default); `load_sessions()` via `SessionsStore` (schema-gated, read-only).
- `src/devin_pm/milestones.py` — `milestone: <name>` session-title tags
  (hidden session → done) + manual `milestones.json` in the project root;
  file wins on name collision; `done_fraction()` accounting.
- `src/devin_pm/report.py` — `# Project: <name>` markdown report
  (`## Sessions` table + `## Milestones`), global report, plain-text
  rollup table for `status`.
- `src/devin_pm/registry.py` — `registry.json` v1 emitter: projects,
  session ids, last-activity ISO, status mix, cost sum, milestone totals.
- `src/devin_pm/cli.py` — thin wrapper: `status [--json]`,
  `report [--project] [--out]`, `milestones --project [--json]`,
  `registry [--out]`. Exit codes: 0 ok · 1 read/parse error · 2 missing
  db / unknown project.
- `docs/SPEC.md` (EN), real READMEs (EN/PT-BR).
- **53 tests, all green** (Windows, Python 3.11.9, pytest 9.1.1) —
  fixtures-first via `devin_internals.fixtures.create_sessions_db()` +
  crafted rows; CLI verified end-to-end on a fixture DB, including a
  read-only check (db bytes unchanged after runs).

## Environment notes

- `python` = 3.11.9 w/ pytest; bare `pip` → Python 3.14. Always
  `python -m pip`.
- exec runs under **cmd.exe**: no heredocs, no multi-line `python -c`;
  commit messages need repeated `-m` flags.
- `devin-internals-spec` is declared as a git dependency
  (`@v0.2.0`) for consumers; locally it's an editable sibling checkout —
  `pip install -e . --no-deps` avoids the network fetch.
- Console glyphs: keep generated CLI output ASCII — `—`/`·` get mangled
  when a cp1252 stdout meets a UTF-8 terminal.

## Decisions / notes

- **Cost is best-effort**: `cogs_json` is unstable (per
  devin-internals-spec SCHEMA.md), so `extract_cost()` sums numeric values
  under cost-ish keys recursively; `null`/`-` = unknown, not zero. Verify
  the real shape on a real DB in M2 before trusting it.
- **Milestone state**: `milestone:`-titled session → done iff `hidden`
  (archive the session to complete the milestone). Manual
  `milestones.json` entries override on name collision.
- **Grouping**: `normalize_path` keys (PM-3) — separators, trailing
  slash, `C:\x` ⇄ `/c/x` ⇄ `/cygdrive/c/x` equivalence, WSL-UNC → POSIX;
  drive-rooted paths fold case (Windows FS semantics), POSIX case kept.
  Original spellings stay in output.
- **Registry has its own subcommand** — `status --json` stays the rollup
  table; `registry` emits the full machine-readable document.

## M2 queue

1. Cost/token aggregation deep-dive — inspect a real `cogs_json` and turn
   `extract_cost()` into per-field extraction (or drop it if the field
   isn't billing).
2. Slack digest integration.
3. GitHub Projects sync.
4. PyPI publish (`pipx install devin-pm`).

## Blockers

None.
