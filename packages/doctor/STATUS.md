# STATUS

## Milestone M1 — done (2026-09-29)

- `src/devin_doctor/model.py` — `Status`/`Finding`/`Context`/`Report`.
  `Context` carries injectable `now_ms` + disk thresholds for deterministic
  tests.
- `src/devin_doctor/paths.py` — platform data-dir detection
  (`%APPDATA%/devin`, `~/Library/Application Support/devin`,
  `~/.config/devin`) and store locators.
- `src/devin_doctor/checks/` — the five M1 checks:
  - `stores` — presence/size/row counts for `sessions.db`,
    `acp-messages/*.db`, `state.vscdb` (via `devin_internals` parsers).
  - `schema` — `detect_schema_version()` on sessions.db (unknown >17 and
    known-but-unsupported <15 both FAIL); shape-gating for the ledger-less
    stores.
  - `health-of-data` — empty sessions, orphan `message_nodes`, sessions
    inactive > `--stale-days`, `SQLITE_BUSY` locks with a "Devin is running"
    hint.
  - `config` — `credentials.toml` presence + TOML validity with values
    masked; `.devin/` `config.json`/`config.local.json`/`mcp_config*.json`/
    `hooks.v1.json` parsed as JSONC and shape-validated (known hook events,
    `{matcher, hooks[]}` groups, `mcpServers` map, legacy `mcpServers` in
    config.json flagged). Checks `ctx.cwd` plus immediate child repos.
  - `disk` — total footprint, top-3 largest stores, acp-messages
    accumulation (count/bytes/mtime span); thresholds on `Context`.
- `doctor.py` — runner (a crashing check degrades to a FAIL finding), text /
  `--json` / `--md` renderers, exit code (1 iff any FAIL).
- `cli.py` — `devin-doctor check` / `devin-doctor report`; thin wrapper.
- Dependency: `devin-internals-spec @ v0.2.0` (git tag). The tag was created
  on the sibling repo's `ad882ec` "Cut 0.2.0" commit and pushed — it did not
  exist on the remote before.
- Tests: 53, all on `devin_internals.fixtures` synthetic trees (healthy +
  broken variants: missing acp dir, `schema_version=99`, corrupt files,
  exclusive-locked DB).

## Verified

- `python -m pytest` — 53 passed (Windows / Python 3.11.9).
- `devin-doctor check` on a generated fixture dir — all PASS, exit 0.
- `devin-doctor check` on a broken fixture (`schema_version=99`, no
  acp/state/credentials) — FAIL + fix lines, exit 1.
- `devin-doctor check` on the real `%APPDATA%/devin` — correct findings:
  schema v17, 36/36 acp DBs recognized, credentials masked, real WARNs
  (751 MiB sessions.db, 109 stale sessions), exit 0.

## M2 queue

- `--fix` autofix for the safe items (e.g. orphan `message_nodes` cleanup,
  stale-session pruning behind a flag, offline VACUUM with backup).
- MCP server checks (probe `mcp_config.json` servers, not just shape).
- Windows-vs-Linux CI matrix verification (workflow exists; confirm green).
- PyPI publish (`pipx install devin-doctor`).
- Candidates noted during M1: `session_locks/*.lock` orphan detection,
  `cli/logs` + `summaries/` size accounting, `--cwd` recursive-depth option.

## Blockers

None.

## Notes / decisions

- Missing `sessions.db` is FAIL (core store); missing `acp-messages` dir and
  `state.vscdb` are WARN — CLI-only installs legitimately lack Desktop data.
- In the schema check, missing stores report WARN "skipped" — the FAIL for a
  missing store lives in `stores`; schema FAILs only on present-but-wrong.
- Devin config files are JSONC — the parser strips `//` and `/* */` comments
  while respecting string literals (URLs in `mcp_config.json` must survive).
- Unknown hook event names → WARN (forward-compatible); malformed hook
  structure → FAIL.
- Stdout/stderr reconfigured to UTF-8 so reports stay clean when piped on
  Windows consoles with legacy codepages.
