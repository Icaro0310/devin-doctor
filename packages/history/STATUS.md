# STATUS — devin-history

Updated: 2026-09-29 · Milestone: **M1 (done)** · Version: 0.1.0

## Done in M1

- Ported both `legacy/` scripts into `src/devin_history/` library modules
  (logic rewritten, scripts not called):
  - `export.py` — `sessions.db` → one note per session + `index.md`
    (`--format json` gives a searchable dump + `index.json`). Idempotent
    via the `last_activity` frontmatter/field marker; `--all`, `--dry-run`.
  - `audit.py` — per-session stats from `message_nodes`/`tool_call_state`,
    inferred status (no final-state column exists), task-type
    classification, anomaly detection (empty / orphan / long-running).
  - `format.py` — pure emitters: session md/json, index, audit md/csv/dict,
    `list` table. Deterministic output (no wall-clock in files).
  - `messages.py`, `times.py`, `paths.py` — tolerant `chat_message`
    decoding, epoch-ms helpers, platform default-store detection.
- `cli.py` thin wrapper: `export` / `audit` / `list`, `--json` on all,
  `--sessions-db` or auto-detect (`%APPDATA%/devin/cli/sessions.db`,
  macOS/Linux equivalents), schema errors exit 2.
- Dependency on `devin-internals-spec` v0.2.0 (schema detector +
  `SessionsStore` parser) — unknown schema versions fail loud.
- 44 tests green (Windows, Python 3.11.9, pytest 9.x). Fixtures generated
  at test time via `devin_internals.fixtures.create_sessions_db`.
- Verified manually: `list`/`export`/`audit` on a v17 fixture DB; second
  `export` run reports `unchanged: 3`; `--csv` writes.
- `docs/SPEC.md` (EN canonical), real READMEs (EN/PT-BR), this file,
  CHANGELOG 0.1.0.

## Environment notes

- `python` = 3.11.9 w/ pytest; bare `pip` → Python 3.14. Always
  `python -m pip`.
- exec runs under **cmd.exe**: no heredocs, no multi-line `python -c`;
  commit messages need repeated `-m`; beware `<`/`>`/`%` in arguments.
- Windows console = cp1252: `cli.main()` reconfigures stdout/stderr to
  utf-8+replace before printing (arrows/emoji would crash otherwise).

## Decisions / notes

- `chat_message` payloads are *unstable* per SCHEMA.md → `messages.py`
  accepts `role`/`content` and `role`/`text` shapes and block lists, maps
  `agent`→`assistant`, returns `None` on non-dict JSON.
- "Orphan" anomaly = `session_id` referenced by child tables but absent
  from `sessions` (SQLite FKs are not enforced); legacy's lock-file orphans
  need `session_locks/` spec coverage (M2).
- GUI `acp-messages/*.db` deferred to M2 — M1 contract covers `sessions.db`
  only; `AcpMessagesStore` is ready in the dependency.
- Export names files `{date}_{session_id}.{fmt}` — atomic, collision-free
  regardless of title.

## Remaining for M2 (per kickoff)

1. `--redact` output pipeline via `devin-redact`.
2. Obsidian vault writer (MOC + folder conventions from the legacy script).
3. SessionEnd hook integration for incremental export.
4. `acp-messages/*.db` (GUI sessions) export/audit via `AcpMessagesStore`.
5. PyPI publish (`pipx install devin-history`).

## Blockers

None.
