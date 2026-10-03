<div align="center">

<img src="assets/banner.svg" alt="devin-search" width="100%"/>

</div>

# devin-search

> **Unofficial community project.** Not affiliated with, endorsed by, or
> sponsored by Cognition AI. "Devin" is a trademark of Cognition AI.

**[Português (BR)](README.pt-BR.md)** · English

Full-text search across all your Devin sessions — find that command, that
error message, that file path or that decision from months ago in under a
second.

## The problem

Devin keeps your entire session history in local SQLite stores
(`sessions.db`, `User/acp-messages/*.db`) — but offers no way to search
across them. You remember Devin fixed a flaky test or ran a specific
`kubectl` command three weeks ago, and the only way back is scrolling
through sessions one by one. Generic `grep` over the raw databases mostly
hits JSON noise and knows nothing about who said what.

## Prior art

- Full-text search over chat/agent history is well-established:
  everything here leans on SQLite's built-in **FTS5** engine with
  **BM25** ranking — the same approach used by ripgrep-style tools,
  mail clients and `sqlite-utils`.
- **tokmesh** and **UniSessions** document/parse the CLI `sessions.db`;
  the schema itself is tracked by
  [`devin-internals-spec`](https://github.com/Icaro0310/devin-internals-spec),
  which this project uses for versioned, read-only access.
- **devin-history** (sibling repo) exports sessions to Markdown/JSON;
  devin-search complements it with instant ranked lookup instead of a
  static dump.

## What makes it Devin-native

Results are **role-tagged and session-linked**, not raw grep hits. The
indexer understands Devin's real message structure through
`devin-internals-spec`'s typed parsers: user prompts vs assistant replies
vs tool calls (including `prompt_history` shell commands and GUI
`acp-messages` sessions), each stamped with its working directory and a
`ref` back to the exact source row. And because the store schema has had
17 migrations already, indexing **fails loudly** on an unknown schema
version instead of silently misreading it.

## Install

Python ≥ 3.10 and `pipx` are required. **Windows (PowerShell):** install `pipx` with `py -m pip install --user pipx`, run `py -m pipx ensurepath`, then reopen the terminal. **Linux (Debian/Ubuntu):** run `sudo apt install pipx python3-venv` and `pipx ensurepath`; reopen the terminal. Other Linux distributions should install `pipx` using their package manager.

```bash
pipx install "devin-search @ git+https://github.com/Icaro0310/devin-search.git"
```

(PyPI release is on the M2 roadmap; Python ≥ 3.10 required.)

## Usage

```bash
# build/update the index (auto-detects Devin's stores; safe to re-run —
# only new rows are indexed each time)
devin-search index

# search everything
devin-search query "kubectl delete pod"

# filters: role, project, date, limit — --json on every command
devin-search query "TypeError" --role assistant --project myrepo
devin-search query "migration" --since 2026-09-01 --limit 5 --json
```

Hits print as `WHEN · ROLE · PROJECT · SESSION · SNIPPET` with the match
wrapped in `«»`; each hit carries a `ref` (e.g. `node:1234`,
`acp:file.db:7`) pointing back to the exact source row.

## Works with Devin alone (Devin-only mode)

devin-search builds and queries a fully local index over Devin's session
stores. Nothing is sent anywhere; the index lives on your disk next to the
data it covers.

## Platform support

Tested on **Windows and Linux** (`windows-latest` + `ubuntu-latest` in CI).
The CLI session DB is auto-detected from `%APPDATA%/devin/cli/sessions.db`
on Windows and `$XDG_DATA_HOME/devin/cli/sessions.db` on Linux (default
`~/.local/share/devin/cli/sessions.db`). ACP logs are searched under
`$XDG_CONFIG_HOME/Devin/User/acp-messages` (default
`~/.config/Devin/User/acp-messages`). A legacy `~/.config/devin` layout is
also checked. Use `--sessions-db` or `--acp-dir` to override.

## Limitations

- **Schema-gated.** Only `sessions.db` schema v15–v17 is accepted; newer
  versions fail loudly (update `devin-internals-spec` first).
- **Opaque payloads.** `chat_message`, `tool_call_*_json` and acp
  `payload` formats are undocumented/unstable — text extraction is
  best-effort and tolerant, not contractual.
- **Keyword search only (M1).** BM25 over tokens — no synonyms or
  embeddings; semantic search is an opt-in M2 candidate.
- **Deletion lag.** New rows are picked up incrementally, but rows
  deleted mid-table upstream can stay in the index until `--rebuild`
  (tail-pruned sources are detected and re-indexed automatically).
- **Read-only by design** — the tool never writes to Devin's stores; the
  only file it creates is `search.db`.

## Development

```bash
pip install -e ".[dev]"
pytest
```

Fixtures are generated at test time by `devin_internals.fixtures` (real
v17 DDL, synthetic rows) — no binary fixtures are committed.

## When to use this

- You remember Devin ran a command, hit an error, touched a file, or made a
  decision, and scrolling sessions one by one is too slow.
- You want ranked results tagged by role (user / assistant / tool call) with
  a `ref` back to the exact source row.
- Your session history must stay on disk — the index is fully local, no
  telemetry, no network calls.
- You want incremental indexing: re-running `devin-search index` only picks
  up new rows.

## When NOT to use this

- You need semantic or synonym-aware search — M1 is keyword BM25 only;
  embeddings are an opt-in M2 candidate.
- You need session *analytics* (cost, tokens, activity) — use `devin-metrics`;
  or relationship queries — use `devin-graph`.
- Your `sessions.db` schema is outside v15–v17 — indexing refuses loudly
  rather than misreading it.

## FAQ

**What is devin-search?** A local full-text search engine over your Devin
session history. It indexes Devin's SQLite stores with FTS5/BM25 and answers
queries like `devin-search query "kubectl delete pod"` in under a second,
with results tagged by role and linked back to the source row.

**Does devin-search send my session data anywhere?** No. Everything runs
locally: it reads Devin's stores read-only and writes a single `search.db`
index next to your data. There are no network calls and no telemetry.

**Does it write to or modify Devin's databases?** No. Devin's stores are
opened read-only by design; the only file devin-search creates is its own
`search.db` index.

**How is this different from `devin-history`?** devin-history exports
sessions to static Markdown/JSON files. devin-search complements it with
instant ranked lookup across all sessions, without exporting anything.

## License

MIT — see [LICENSE](LICENSE).
