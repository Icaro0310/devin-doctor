# KICKOFF M1 — devin-history

You are the dedicated session for THIS repository. The scaffold comes from
the ecosystem template — fill it with real content. Rules:

- Read `docs/SPEC.pt-BR.md` style is NOT required — write `docs/SPEC.md` in
  English directly (canonical); keep shared content in `README.md` and
  Windows/Linux install, path, and troubleshooting details in the OS guides.
- Logic lives in `src/devin_history/`; `cli.py` is a thin wrapper.
- Fixtures first (TDD), small logical commits,
  `Co-Authored-By: Devin <158243242+devin-ai-integration[bot]@users.noreply.github.com>`,
  `git push` at the end, `STATUS.md` + `CHANGELOG.md` updated.

## What this project is (one sentence)

Export and audit Devin Desktop session history — turns the local
`sessions.db` into Markdown notes, a searchable JSON dump, and an
Obsidian-ready vault folder.

## Prior art / base material

`legacy/` contains two proven scripts from the orchestrator workspace —
**port them, don't call them**:

- `devin-history-export.py` — sessions.db → Obsidian markdown notes
  (idempotent, one note per session + index).
- `audit_sessions.py` — full-session audit: status, task type, repo,
  workspace, period, complexity, incidents, orphans → CSV + report.

Rewrite their logic as library modules in `src/devin_history/`:
`export.py`, `audit.py`, `format.py` (markdown/json emitters).

## Devin-native differentiator (the "extra")

Understands Devin's real stores: uses **`devin-internals-spec`** for schema
detection + typed parsers instead of raw SQL guessing. Add to
`pyproject.toml`:

```toml
dependencies = [
  "devin-internals-spec @ git+https://github.com/Icaro0310/devin-internals-spec.git@v0.2.0",
]
```

and `python -m pip install -e .` will pull it. Import `devin_internals`
(schema detect, SessionsStore parser) — fail loud on unknown schema.

## CLI contract

- `devin-history export --sessions-db <path> --out <dir> [--format md|json]`
  — idempotent (skip unchanged), one file per session + `index.md`.
- `devin-history audit --sessions-db <path> [--csv out.csv]` — grouping by
  status/type/repo/period + anomaly list (empty sessions, orphans,
  long-running).
- `devin-history list [--sessions-db <path>] [--limit N]` — quick table.
- Auto-detect default store location on Windows
  (`%APPDATA%/devin/cli/sessions.db`) and Linux; `--json` on all commands.

## Fixtures

Use `devin_internals.fixtures.create_sessions_db()` to generate the v17
fixture in tmp dirs for tests — no committed binary fixtures needed.

## Tests (required green)

- export produces one note per fixture session + index; rerun is idempotent;
- audit groups correctly + flags the fixture's anomalies;
- `list`/`--json` output shapes; unknown schema version fails loud;
- no writes to source DB (`mode=ro` everywhere).

## Environment notes

- `python` = 3.11.9 w/ pytest; use `python -m pip` (bare `pip` = Py3.14).
- Multi-line `python -c` produces no output — use script files.
- Windows shell; avoid heredocs.

## Done criteria

All tests green · CLI verified manually on a fixture DB · READMEs +
SECURITY.md + CHANGELOG + STATUS.md real content · pushed.
M2 queue in STATUS.md: `--redact` via devin-redact, Obsidian vault writer,
SessionEnd hook, PyPI.
