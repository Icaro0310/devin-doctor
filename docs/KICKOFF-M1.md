# KICKOFF M1 — devin-doctor

You are the dedicated session for THIS repository. The scaffold comes from
the ecosystem template — fill it with real content. Rules:

- Write `docs/SPEC.md` in English directly; keep shared content in `README.md`
  and Windows/Linux install, path, and troubleshooting details in the OS guides.
- Logic lives in `src/devin_doctor/`; `cli.py` thin wrapper.
- Small commits, trailer
  `Co-Authored-By: Devin <158243242+devin-ai-integration[bot]@users.noreply.github.com>`,
  `git push` at the end, `STATUS.md` + `CHANGELOG.md` updated.

## What this project is (one sentence)

`devin-doctor` diagnoses a Devin Desktop installation — one command that
checks the stores, schema versions, config files, disk usage and common
breakage, then prints a health report with concrete fix suggestions.

## The checks (each = one module in `src/devin_doctor/checks/`)

1. **stores** — locate `cli/sessions.db`, `User/acp-messages/*.db`,
   `User/globalStorage/state.vscdb` (Windows `%APPDATA%/devin` + Linux
   paths); report present/missing, sizes, row counts.
2. **schema** — `devin_internals.detect_schema_version()` per store →
   OK / unknown-version / unsupported with explanation.
3. **health-of-data** — empty sessions count, orphan message_nodes,
   sessions older than N days, DBs locked (`SQLITE_BUSY`) with hint that
   Devin is running.
4. **config** — `credentials.toml` present (mask — never print values),
   `.devin/` hooks/mcp config sanity in cwd repos.
5. **disk** — total Devin data dir size, largest DBs, `acp-messages`
   accumulation trend.

Use `devin-internals-spec` for detection/parsers — add to `pyproject.toml`:

```toml
dependencies = [
  "devin-internals-spec @ git+https://github.com/Icaro0310/devin-internals-spec.git@v0.2.0",
]
```

## Output contract

- `devin-doctor check [--data-dir <path>] [--json]` — every check prints
  `PASS/WARN/FAIL` + one-line finding + `fix:` suggestion. Exit 0 all-PASS,
  1 any-FAIL.
- `devin-doctor report [--md]` — same as markdown for pasting into issues.
- Never write to any Devin store or config — read-only, always.

## Fixtures/tests

Generate v17 fixtures via `devin_internals.fixtures` in tmp dirs; build a
"broken" fixture variant (missing acp-messages dir, unknown schema_version
via the fixture's `schema_version` knob). Tests: each check returns the
right status on healthy vs broken fixtures; `--json` schema; exit codes.

## Environment notes

- `python` = 3.11.9 w/ pytest; `python -m pip` only (bare `pip` = Py3.14).
- Multi-line `python -c` produces no output — use script files.

## Done criteria

All tests green · `devin-doctor check` verified on a fixture data-dir ·
READMEs + SECURITY.md + CHANGELOG + STATUS.md real content · pushed.
M2 queue in STATUS.md: `--fix` autofix for safe items, MCP server checks,
Windows-vs-Linux matrix, PyPI.
