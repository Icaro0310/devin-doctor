# SPEC — devin-doctor (M1)

## 1. Problem

A Devin Desktop/CLI installation keeps a non-trivial amount of local state —
a 700+ MiB `sessions.db` with a versioned schema, one `acp-messages/*.db` per
GUI session, a VS Code-style `state.vscdb`, `credentials.toml`, JSONC config
files — and **nothing tells you when it is broken or bloated**. Symptoms
appear downstream (missing history, auth failures, giant disk usage) long
after the root cause. There is no equivalent of `brew doctor` for Devin.

## 2. What it does

One read-only command that diagnoses the installation and prints a health
report with concrete `fix:` suggestions:

```
devin-doctor check [--data-dir P] [--cwd P] [--stale-days N] [--json]
devin-doctor report [--data-dir P] [--cwd P] [--stale-days N] [--md]
```

## 3. The five checks

| check | what it reports |
|---|---|
| `stores` | presence/absence, size and row counts of `cli/sessions.db`, `User/acp-messages/*.db`, `User/globalStorage/state.vscdb` |
| `schema` | `detect_schema_version()` on sessions.db (known/unknown/unsupported); table-shape recognition for the ledger-less stores |
| `health-of-data` | empty sessions, orphan `message_nodes`, sessions inactive > N days, `SQLITE_BUSY` locked DBs (Devin running) |
| `config` | `credentials.toml` presence + TOML validity (**values never printed**); JSONC validity and shape of `.devin/` hooks/MCP config in cwd and immediate child repos |
| `disk` | total data-dir size, top-3 largest DBs, `acp-messages` accumulation (count/bytes/mtime span) |

Status semantics: `PASS` healthy · `WARN` degraded or suspicious · `FAIL`
broken/unreadable. Exit code `0` unless any finding is `FAIL` (then `1`).

## 4. Hard rules

- **Read-only, always.** Every store is opened `mode=ro`; nothing is ever
  written to the data dir.
- **No row content in output.** Counts, sizes, versions, paths only.
  `credentials.toml` reports section/key counts — never values.
- **Detection via `devin-internals-spec`**, not ad-hoc SQL — schema versions
  and table shapes come from the spec library so this tool inherits its
  fail-loud behavior on unknown schemas.

## 5. Data-dir detection

Windows: `%APPDATA%\devin` · macOS: `~/Library/Application Support/devin` ·
Linux: `$XDG_CONFIG_HOME/devin` or `~/.config/devin`. `--data-dir` overrides.

## 6. Non-scope (M1)

- No autofix (`--fix` is M2): suggestions are printed, never applied.
- No session-content analysis (that is `devin-history`).
- No MCP server probing / plugin checks (M2).
