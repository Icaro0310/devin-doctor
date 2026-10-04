# SPEC — devin-pm

## 1. Problem

Devin keeps every CLI session in a local `sessions.db`, but gives you no
project-level view of that history. After a few weeks the database holds a
hundred sessions and there is no way to answer the basic PM questions: *what
did I work on per repository? what is the state of project X? what did we
say we would finish?*

The orchestrator workspace already proved the idea once — a lifetime audit
(`sessions_report.md` / `sessions_summary.csv`) grouped 100+ sessions by
`working_directory` and produced something a human could actually read.
This repo turns that one-off script into a maintained tool.

## 2. Devin extra (and the 3 tests)

**Extra:** it turns Devin's session store into project-management artifacts
— per-project rollup, markdown status reports, milestone tracking and a
machine-readable `registry.json` — that simply do not exist anywhere in
the base tool.

- **Side-by-side:** Devin CLI/Desktop lists sessions, but cannot group them
  by repository, cannot tag a session as a milestone marker, and cannot emit
  a project registry. `devin-pm` does something the base tool cannot do at
  all.
- **No-Devin:** remove Devin and there is no `sessions.db` to read — the
  extra disappears entirely.
- **One sentence:** *"It's a project manager over your Devin sessions —
  it reads `sessions.db` and gives you per-repo status, milestones and a
  registry."*

## 3. Scope (M1)

- `projects.py` — group sessions by `working_directory` → project model
  (name = dir basename, session count, last activity, status mix,
  `session_ids`, best-effort cost).
- `report.py` — markdown status report per project or global; plain-text
  rollup table for `status`.
- `milestones.py` — `milestone:` session-title tags + manual
  `milestones.json` per project root; done/pending accounting.
- `registry.py` — emit `registry.json` (same spirit as the ecosystem hub
  registry in devin-powerups).
- `cli.py` — thin wrapper: `status`, `report`, `milestones`, `registry`,
  `verify`.
- `verify.py` — cross-check tracked projects against the ecosystem hub
  registry (`devin-powerups/registry.json`): entries unknown to pm,
  pm-tracked projects missing from the registry (ecosystem-shaped ones
  count as drift), and name/description/url drift read from the checkout's
  `pyproject.toml` and git `origin`. Exit 1 on drift.

Post-M1:

- `vscdb.py` (PM-1) — GUI session→workspace bindings from
  `state.vscdb`'s `ItemTable` (`windsurfSpace.sessionWorkspace/<backend>/
  <slug>` → `{workspaceId, label, folders[], lastUpdated}`) →
  `GuiSession`, a Session-shaped record (`status`/`source` = `gui`, no
  transcript) that merges into the same grouping. `--vscdb [PATH]` on all
  subcommands; auto-detect `<config>/Devin/User/globalStorage/
  state.vscdb` or `DEVIN_PM_STATE_VSCDB`.
- `paths.py` (PM-3) — `normalize_path()` grouping key: `C:\x` ⇄ `/c/x` ⇄
  `/cygdrive/c/x` (drive-rooted paths case-folded), WSL-UNC → in-distro
  POSIX, separator collapse. Display keeps original paths; POSIX case
  preserved.

### Non-scope (M1)

- No writes to `sessions.db`, ever — `mode=ro` only.
- No GUI/Desktop session sources (`acp-messages/*.db`) — CLI sessions
  only. *(Post-M1: `state.vscdb` workspace bindings are covered via
  `--vscdb`; GUI transcripts remain out of scope.)*
- No task classification or token analytics (heuristics live in the legacy
  audit script; M2 candidates).
- No remote sync (GitHub Projects, Slack) — M2+.

## 4. Data contract

### Project model

| field | source | notes |
|---|---|---|
| `name` | basename of `working_directory` | separators normalized, case preserved |
| `working_directory` | `sessions.working_directory` | normalized (`\`→`/`, trailing sep stripped) |
| `session_count` / `session_ids` | grouped `sessions.id` | |
| `gui_session_count` | `source == "gui"` members | PM-1: state.vscdb bindings |
| `last_activity` | `max(last_activity_at)` | epoch ms → ISO-8601 UTC |
| `status` | `hidden` flag | `active` / `hidden` / `gui` |
| `cost` | `sessions.cogs_json` | **best-effort**: `cogs_json` is unstable; we sum numeric values under cost-ish keys (`cost*`, `*usd`, `credits*`, `amount`, `spent`) and return `null` when nothing recognizable exists. `null` = unknown, not zero. |

### Milestones

- Session title `milestone: <name>` (case-insensitive) declares a milestone
  in that session's project. `hidden` session → **done**; active → pending.
  Archiving the session is how you complete the milestone.
- `<working_directory>/milestones.json` holds manual entries:
  `{"milestones": [{"name": "X", "done": true}, "Y"]}` (bare list and bare
  strings accepted; strings are pending).
- Merge rule: file entries and detected sessions dedup by name
  (case-insensitive); **the file wins**.

### registry.json

```json
{
  "$schema": "https://github.com/Icaro0310/devin-pm/registry.schema.json",
  "version": 1,
  "generated": "2026-09-29T00:00:00Z",
  "source": {"sessions_db": "...", "state_vscdb": "...",
             "schema_version": 17},
  "projects": [
    {
      "name": "devin-pm",
      "working_directory": "C:/.../devin-pm",
      "sessions": 3,
      "gui_sessions": 1,
      "session_ids": ["..."],
      "last_activity": "2026-09-29T19:00:00Z",
      "status": {"active": 2, "hidden": 1},
      "cost": null,
      "milestones": {"total": 2, "done": 1, "pending": 1}
    }
  ],
  "totals": {"projects": 1, "sessions": 3, "cost": null}
}
```

## 5. CLI

```
devin-pm status     [--sessions-db PATH] [--vscdb [PATH]] [--json]
devin-pm report     [--sessions-db PATH] [--vscdb [PATH]]
                    [--project NAME] [--out FILE]
devin-pm milestones [--sessions-db PATH] [--vscdb [PATH]]
                    --project NAME [--json]
devin-pm registry   [--sessions-db PATH] [--vscdb [PATH]] [--out FILE]
devin-pm verify     [--sessions-db PATH] [--vscdb [PATH]]
                    [--registry PATH] [--pm-registry FILE] [--json]
```

- `--sessions-db` default: `DEVIN_PM_SESSIONS_DB` env var, else platform
  default (`%APPDATA%/devin/cli/sessions.db` on Windows,
  `~/Library/Application Support/devin/...` on macOS, XDG on Linux).
- `--vscdb` merges GUI sessions: bare flag auto-detects
  `<config>/Devin/User/globalStorage/state.vscdb` (or
  `DEVIN_PM_STATE_VSCDB`); a missing auto-detected store warns and
  continues CLI-only, a missing explicit `PATH` exits `2`.
- `report` without `--project` emits a global report over all projects.
- `registry` writes to stdout unless `--out` is given.
- Exit codes: `0` ok · `1` read/parse error (bad db, malformed
  milestones.json, schema errors; `verify` also returns `1` on drift) ·
  `2` usage-level (db missing, unknown project, missing inputs).

## 6. Fixtures and tests

- `devin_internals.fixtures.create_sessions_db()` into tmp dirs — real v17
  DDL, synthetic rows only.
- Tests craft sessions with distinct `working_directory` values (including
  a trailing-separator variant), a `milestone:`-titled hidden session, an
  active `milestone:` session, and `cogs_json` cost payloads.
- Coverage: grouping/normalization, project rollup fields, report sections,
  milestone detect/file/merge/done-%, registry shape + totals, CLI exit
  codes, read-only guarantee (db bytes unchanged after CLI runs).

## 7. Risks and mitigation

| Risk | Mitigation |
|---|---|
| `sessions.db` schema changes | `SessionsStore` gates on `detect_schema_version` — fails loudly on unknown versions |
| `cogs_json` inner format is unstable | cost extraction is best-effort, returns `null` when unrecognized |
| Two real dirs differ only by case | POSIX paths keep case; drive-rooted paths fold (Windows FS is case-insensitive — PM-3) |
| Reading user data | read-only, zero network, never copies row content into output — only ids, titles, dirs, counts |

## 8. M2 queue

- Cost/token aggregation deep-dive (verify real `cogs_json` shape on a real
  DB, per-field extraction).
- Slack digest integration.
- GitHub Projects sync.
- PyPI publish.
