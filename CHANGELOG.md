# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `vscdb` — GUI sessions from the Desktop `state.vscdb` `ItemTable`
  (PM-1): `windsurfSpace.sessionWorkspace/<backend>/<slug>` bindings →
  `GuiSession` records, grouped by `workspaceId`/`folders`/`label` into
  the same projects as `sessions.db` rows. `--vscdb [PATH]` on every
  subcommand (bare flag auto-detects, `DEVIN_PM_STATE_VSCDB` overrides);
  gui sessions are marked `gui` in status/report output and counted as
  `gui_sessions` in JSON/registry. Read-only (`mode=ro`).
- `paths` — `normalize_path()` grouping key (PM-3): `C:\x` ⇄ `C:/x` ⇄
  `/c/x` ⇄ `/cygdrive/c/x` drive equivalence with case folding on
  drive-rooted paths, `\\wsl.localhost\<distro>\…`/`\\wsl$\…` → in-distro
  POSIX path, separator/duplicate/trailing-slash normalization. Grouping
  key only — display keeps original paths; POSIX case preserved.

## [0.1.0] - 2026-09-29

### Added

- Initial scaffold from `devin-repo-template`.
- `projects` — group `sessions.db` sessions by `working_directory` into a
  project model (name, session count/ids, last activity, status mix,
  best-effort cost).
- `milestones` — `milestone:` session-title tags + per-project
  `milestones.json`; done/pending accounting.
- `report` — markdown status report per project or global, plus the
  plain-text rollup table.
- `registry` — machine-readable `registry.json` emitter (v1).
- `devin-pm` CLI: `status`, `report`, `milestones`, `registry`
  subcommands; `%APPDATA%/devin/cli/sessions.db` auto-detect;
  `DEVIN_PM_SESSIONS_DB` override; read-only always.
- `docs/SPEC.md` with the M1 data contracts; real READMEs (EN/PT-BR).
