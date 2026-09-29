# Security Policy

## What this tool does with your data

- **No telemetry.** This project sends nothing anywhere.
- **No network.** All processing is local; there is no network code path.
- **Read-only.** It opens Devin's stores with SQLite `mode=ro` and never
  writes to the data dir or to any config file.
- **What it reads:** the Devin data dir (`%APPDATA%\devin` on Windows,
  `~/.config/devin` on Linux, `~/Library/Application Support/devin` on
  macOS) — `cli/sessions.db`, `User/acp-messages/*.db`,
  `User/globalStorage/state.vscdb`, `credentials.toml`, `config.json`,
  `mcp_config.json` — plus `.devin/` config files under the working
  directory.
- **What it prints:** counts, sizes, schema versions and paths only — never
  row content. `credentials.toml` is parsed for validity; only section/key
  counts are reported, values are never shown.

## Sensitive data handling

- Output intended for sharing must pass through
  [`devin-redact`](https://github.com/Icaro0310/devin-redact) before publication.
- Never commit Devin session databases, `.env` files, tokens, or pairing codes.

## Reporting a vulnerability

Open a **private** security advisory on GitHub, or open an issue marked
`[SECURITY]` **without** including the vulnerable data itself.

Do not file public issues containing secrets, tokens, or session content.
