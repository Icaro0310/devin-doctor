# STATUS — devin-search

Updated: 2026-09-29 · Milestone: **M1 (done)** · Version: 0.1.0

## Done in M1

- `src/devin_search/` library modules (logic lives here; `cli.py` is a thin
  argparse wrapper):
  - `index.py` — `build_index()`: one FTS5 `docs` table (text + UNINDEXED
    metadata columns) in `search.db`; incremental via `index_meta`
    watermarks (`max row_id`/`id`/`position` per source, ref-dedup for
    `tool_call_state` which has no auto-increment id). Shrunk sources are
    detected (max < watermark → drop + re-index) and deleted acp files get
    their docs removed. `--rebuild` forces a fresh index.
  - `query.py` — `search()`: FTS5 `bm25()` ranking + `snippet()`
    highlighting (`«»`), filters `role`/`project`/`since`; `to_fts_query`
    escapes user input to quoted tokens so FTS operators can't inject.
  - `fmt.py` — pure emitters: `WHEN · ROLE · PROJECT · SESSION · SNIPPET`
    table, JSON dicts, index stats.
  - `extract.py` — tolerant payload → `(role, text)`; handles
    `role`/`content`/`text` shapes, block lists, recursive string walk
    fallback, role normalization (`agent`/`thought` → `assistant`,
    `tool_call` → `tool`, `is_shell` prompts → `shell`).
  - `paths.py` — platform defaults: `%APPDATA%/devin/cli/sessions.db`,
    `…/User/acp-messages`, index at `<app-dir>/devin-search/search.db`.
- Sources indexed: `message_nodes`, `prompt_history`, `tool_call_state`
  (sessions.db) + acp `messages` (payload text walk; session_id/created
  sniffed from `meta`, project/title joined from sessions.db when both are
  indexed). Hits carry `ref` back to the source row
  (`node:<row_id>` · `prompt:<id>` · `tool:<sid>/<tcid>` ·
  `acp:<file>:<pos>`).
- Dependency on `devin-internals-spec` v0.2.0 — all source reads go through
  `SessionsStore`/`AcpMessagesStore` (`mode=ro`); unknown schema versions
  fail loud (CLI exit 2).
- 35 tests green (Windows, Python 3.11.9, pytest 9.1.1) — fixtures
  generated at test time via `devin_internals.fixtures`; no binaries
  committed. Source stores asserted byte-identical (sha256).
- Verified manually: `index` → `+31 docs` on the fixture tree, re-run
  `+0`, `query "fixture message"` ranked table, `--json` shape, `--role`.
- `docs/SPEC.md` (EN canonical), real READMEs (EN/PT-BR), this file,
  CHANGELOG 0.1.0.

## Environment notes

- `python` = 3.11.9 w/ pytest; bare `pip` → Python 3.14. Always
  `python -m pip`.
- exec runs under **cmd.exe**: no heredocs, no multi-line `python -c`;
  commit messages need repeated `-m`.
- Windows console = cp1252: `cli.main()` reconfigures stdout/stderr to
  utf-8+replace (snippet markers `«»` would print mangled otherwise).
- sqlite3 on this Python ships FTS5 (verified: `CREATE VIRTUAL TABLE …
  USING fts5` works; `bm25()`/`snippet()` available).

## Decisions / notes

- FTS5 table stores all columns directly (no external-content table) —
  simpler deletes/inserts at this scale; `UNINDEXED` keeps filter columns
  out of the token stream.
- acp `meta` key names are unstable → session id/created are sniffed by
  substring match (`session_id`, `created`); missing → filename stem / 0.
- acp positions are 0-based → watermark default is `-1`, not `0`.
- "Session link" for M1 = `session_id` + `ref` fields; a clickable
  open-in-Devin link is M2 (needs the app's deep-link scheme).
- Mid-table upstream deletions are not tracked (documented limitation);
  tail-prune drift IS detected and self-heals.

## Remaining for M2 (per kickoff)

1. TUI/browser result viewer; open-in-Devin session links.
2. Obsidian link output for hits.
3. Opt-in semantic search (embeddings sidecar alongside FTS).
4. PyPI publish (`pipx install devin-search`).

## Blockers

None.
