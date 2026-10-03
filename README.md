<div align="center">

<img src="assets/banner.svg" alt="devin-history" width="100%"/>

<a href="https://github.com/Icaro0310/devin-history/actions/workflows/tests.yml"><img src="https://github.com/Icaro0310/devin-history/actions/workflows/tests.yml/badge.svg" alt="tests"/></a>


</div>

# devin-history

> **Unofficial community project.** Not affiliated with, endorsed by, or
> sponsored by Cognition AI. "Devin" is a trademark of Cognition AI.

**[Português (BR)](README.pt-BR.md)** · English

Export and audit Devin Desktop session history — turns the local
`sessions.db` into Obsidian-ready Markdown notes, a searchable JSON dump,
and an audit report.

## The problem

Devin Desktop keeps your session history in a local SQLite database
(`%APPDATA%/devin/cli/sessions.db` on Windows, or
`$XDG_DATA_HOME/devin/cli/sessions.db` on Linux; default
`~/.local/share/devin/cli/sessions.db`) — and nowhere else. There is no export
button: once a session scrolls out of the UI (or is pruned by the app), the
prompts, replies and tool calls are effectively gone. You can't search old
sessions, can't answer "what did I ask Devin to do last month", and can't
audit how the agent has been used across projects.

## Prior art

- **tokmesh** and **UniSessions** document/parse `sessions.db`; the schema
  itself is tracked by [`devin-internals-spec`](https://github.com/Icaro0310/devin-internals-spec).
- This project ports two proven scripts that lived in the orchestrator
  workspace (`legacy/`): `devin-history-export.py` (DB → Obsidian notes) and
  `audit_sessions.py` (lifetime audit → CSV + report). They are rewritten
  as library modules — same logic, real tests.
- You can also just run `sqlite3` queries by hand — but then you guess the
  schema on every Devin update.

## What makes it Devin-native

It understands Devin's real stores instead of raw-SQL guessing: it opens
`sessions.db` through `devin-internals-spec`'s typed parsers and **refuses
loudly** when the schema version is one it has never seen (the store has
had 17 migrations already). The export knows about `hidden` sessions,
interrupted threads (last node = user), `tool_call_state` failures and
epoch-millisecond timestamps — details a generic SQLite dump misses.

## Install

Python ≥ 3.10 and `pipx` are required. **Windows (PowerShell):** install `pipx` with `py -m pip install --user pipx`, run `py -m pipx ensurepath`, then reopen the terminal. **Linux (Debian/Ubuntu):** run `sudo apt install pipx python3-venv` and `pipx ensurepath`; reopen the terminal. Other Linux distributions should install `pipx` using their package manager.

```bash
pipx install "devin-history @ git+https://github.com/Icaro0310/devin-history.git"
```

(PyPI release is on the M2 roadmap; Python ≥ 3.10 required.)

## Usage

```bash
# quick session table (auto-detects %APPDATA%/devin/cli/sessions.db)
devin-history list

# one Obsidian note per session + index.md — safe to re-run (incremental)
devin-history export --out ~/ObsidianVault/Sessions

# searchable JSON dump instead of Markdown
devin-history export --out dump/ --format json

# audit: status/type/project/period groupings + anomalies, optional CSV
devin-history audit --csv audit.csv

# everything has --json; point at a specific DB with --sessions-db
devin-history audit --sessions-db path/to/sessions.db --json
```

Notes are idempotent: each file embeds the session's `last_activity`
marker, so re-runs skip unchanged sessions (`--all` forces a rewrite,
`--dry-run` previews).

## Works with Devin alone (Devin-only mode)

Everything devin-history does happens on your machine: it reads
`sessions.db` and writes Markdown/JSON exports to a folder you choose. No
network, no external service — the Obsidian-style note layout is just a
format, Obsidian itself is not required.

One caution for restricted machines: exports contain raw prompts, paths and
commands, which may include secrets. Keep the export folder private, define a
retention rule, and run
[`devin-redact`](https://github.com/Icaro0310/devin-redact) before sharing an
export.

## Platform support

Tested on **Windows and Linux** (`windows-latest` + `ubuntu-latest` in CI).
The CLI session database is auto-detected: `%APPDATA%/devin/cli/sessions.db`
on Windows and `$XDG_DATA_HOME/devin/cli/sessions.db` on Linux (default
`~/.local/share/devin/cli/sessions.db`). A legacy `~/.config/devin` location
is also checked. macOS uses `~/Library/Application Support/devin/`. Override
with `--sessions-db` (see Usage).

## Limitations

- **Schema-gated.** Only `sessions.db` schema v15–v17 is accepted; anything
  newer fails loudly rather than misreading (update `devin-internals-spec`
  first).
- **Opaque payloads.** `chat_message` and `tool_call_*_json` inner formats
  are undocumented and unstable — decoding is best-effort and tolerant, not
  contractual.
- **Inferred status.** The DB has no final-state column; "completed" /
  "interrupted" / "abandoned" are heuristics (see `docs/SPEC.md` §4).
- **No billing.** Token/cost data is not stored locally; only
  `num_tokens_preceding` (context size) exists.
- **CLI sessions only (M1).** GUI sessions under `User/acp-messages/*.db`,
  session locks and log correlation are planned for M2.
- **Read-only by design** — the tool never writes to Devin's stores.

## Development

```bash
pip install -e ".[dev]"
pytest
```

Fixtures are generated at test time by `devin_internals.fixtures` (real v17
DDL, synthetic rows) — no binary fixtures are committed.

## License

MIT — see [LICENSE](LICENSE).
