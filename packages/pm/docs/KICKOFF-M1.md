# KICKOFF M1 — devin-pm

You are the dedicated session for THIS repository. The scaffold comes from
the ecosystem template — fill it with real content. Rules:

- Write `docs/SPEC.md` in English directly; keep shared content in `README.md`
  and Windows/Linux install, path, and troubleshooting details in the OS guides.
- Logic lives in `src/devin_pm/`; `cli.py` thin wrapper.
- Small commits, trailer
  `Co-Authored-By: Devin <158243242+devin-ai-integration[bot]@users.noreply.github.com>`,
  `git push` at the end, `STATUS.md` + `CHANGELOG.md` updated.

## What this project is (one sentence)

`devin-pm` is a project manager over your Devin sessions — it reads
`sessions.db`, groups work per repository/project, and generates
status reports, milestones and a machine-readable project registry.

## Prior art / base material

The orchestrator workspace proved the idea with `sessions_report.md` /
`sessions_summary.csv` (a lifetime audit of 100+ sessions grouped by
project). This repo turns that into a maintained tool.

Use `devin-internals-spec` for schema detection + `SessionsStore` parser:

```toml
dependencies = [
  "devin-internals-spec @ git+https://github.com/Icaro0310/devin-internals-spec.git@v0.2.0",
]
```

## Feature scope (M1)

`src/devin_pm/`:
- `projects.py` — group sessions by `working_directory` → project model
  (name = dir basename, session count, last activity, status mix,
  `session_ids` list).
- `report.py` — markdown status report per project or global
  (`# Project`, `## Sessions`, table of id/title/date/status/cost).
- `milestones.py` — `milestones.json` per project: a session can be tagged
  `milestone:` in its title, or milestones listed manually in the file;
  report shows done/pending.
- `registry.py` — emit `registry.json` (machine-consumable, same spirit as
  the ecosystem hub registry): projects, sessions, last-activity, cost sum.

## CLI contract

- `devin-pm status [--sessions-db <path>] [--json]` — per-project rollup table.
- `devin-pm report --project <name> [--out file.md]` — markdown report.
- `devin-pm milestones --project <name>` — list + done %.
- Auto-detect `%APPDATA%/devin/cli/sessions.db`; read-only always.

## Fixtures/tests

`devin_internals.fixtures.create_sessions_db()` in tmp dirs; craft sessions
with distinct `working_directory` values + a `milestone:` titled session.
Tests: grouping, report sections, milestones done %, registry JSON shape,
exit codes.

## Environment notes

- `python` = 3.11.9 w/ pytest; `python -m pip` only (bare `pip` = Py3.14).
- Multi-line `python -c` produces no output — use script files.

## Done criteria

All tests green · CLI verified on fixture DB · READMEs + SECURITY.md +
CHANGELOG + STATUS.md real content · pushed.
M2 queue in STATUS.md: cost/token aggregation deep-dive, Slack digest
integration, GitHub Projects sync, PyPI.
