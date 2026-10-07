# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- README install section replaced by a generated `DIST-STATUS` banner stating the tool is source-only (no PyPI release yet) and offering both `pipx` and `uv` source installs.

- `llms.txt` no longer states a hard-coded ecosystem size; the registry owns the count.

## [0.1.0] - 2026-09-29

### Added

- Initial scaffold from `devin-repo-template`.
- `devin-search index` — builds a local SQLite FTS5 index (`search.db`)
  from `sessions.db` (`message_nodes`, `prompt_history`, `tool_call_state`)
  and `User/acp-messages/*.db`; incremental via per-source watermarks,
  `--rebuild`, `--json`. Source stores are opened read-only through
  `devin-internals-spec` v0.2.0 and unknown schema versions fail loudly.
- `devin-search query <term>` — BM25-ranked hits with highlighted
  snippets, role/project/since/limit filters and `--json`; each hit links
  back to its source row via `ref`.
