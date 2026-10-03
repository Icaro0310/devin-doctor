<div align="center">

<img src="assets/banner.svg" alt="devin-graph" width="100%"/>

</div>

# devin-graph

> **Unofficial community project.** Not affiliated with, endorsed by, or
> sponsored by Cognition AI. "Devin" is a trademark of Cognition AI.

**[Português (BR)](README.pt-BR.md)** · English

A knowledge graph over Devin sessions: sessions, projects, files and tools
become nodes — queryable ("which sessions touched file X?", "which tools does
project Y depend on?") and exportable for visualization.

## The problem

After dozens of Devin sessions you lose the thread: which sessions touched
that config file, which tools a project relies on, which projects share the
same files. The data exists in `sessions.db` (`tool_call_state` records every
call the agent made) but there is no way to query across sessions — only
per-session scrolling in the UI.

## Prior art

- Code-knowledge graphs (Sourcegraph, Glean-style indexes) map *code*, not
  *agent activity*; they don't know what your AI sessions touched.
- `devin-internals-spec` provides the schema + typed read-only parsers this
  tool builds on; `devin-history` exports the same store to notes but has no
  cross-session structure.
- You could hand-write SQL — but the `tool_call_json` payload format is
  undocumented and changes; here it's extracted defensively in one place.

## What makes it Devin-native

Edges come from **ground truth, not prose**: `file_touched` edges are
extracted from `tool_call_state` payloads (file paths in fs/terminal tool
calls) and anchored to the session's `working_directory`. That data simply
doesn't exist outside Devin's store — remove Devin and there is no graph to
build. Schema drift is gated by `devin-internals-spec`'s version detector.

## Install

Python ≥ 3.10 and `pipx` are required. **Windows (PowerShell):** install `pipx` with `py -m pip install --user pipx`, run `py -m pipx ensurepath`, then reopen the terminal. **Linux (Debian/Ubuntu):** run `sudo apt install pipx python3-venv` and `pipx ensurepath`; reopen the terminal. Other Linux distributions should install `pipx` using their package manager.

```bash
pipx install "devin-graph @ git+https://github.com/Icaro0310/devin-graph.git"
```

(PyPI release is on the M2 roadmap; Python ≥ 3.10 required.)

## Usage

```bash
# build the graph (auto-detects the Devin sessions.db for your OS) — safe to
# re-run: unchanged sessions are skipped
devin-graph build --graph graph.db

# canned queries
devin-graph query file "src/app.py"        --graph graph.db
devin-graph query tool "execute"           --graph graph.db
devin-graph query project "my-repo"        --graph graph.db
devin-graph query projects-graph           --graph graph.db --json

# D3-friendly dump: {"meta", "nodes", "edges"}
devin-graph export --format json --graph graph.db --out graph.json
```

Matching is forgiving (`src/app.py` finds `/repo/alpha/src/app.py`);
everything has `--json`. The source DB is opened `mode=ro` and never
written — tests assert its hash is unchanged.

## Works with Devin alone (Devin-only mode)

devin-graph builds `graph.db` locally from Devin's session stores — the whole
pipeline is offline. Note that the derived database contains the same
sensitive content as the sessions themselves (prompts, paths, commands):
keep it private like the originals.

## Platform support

Tested on **Windows and Linux** (`windows-latest` + `ubuntu-latest` in CI).
The CLI session DB is auto-detected: `%APPDATA%/devin/cli/sessions.db` on
Windows and `$XDG_DATA_HOME/devin/cli/sessions.db` on Linux (default
`~/.local/share/devin/cli/sessions.db`). A legacy `~/.config/devin` location
is also checked. Pass `--sessions-db` to override.

## Limitations

- **Schema-gated.** Only `sessions.db` schema v15–v17; newer fails loudly
  (update `devin-internals-spec` first).
- **Heuristic path extraction.** `tool_call_*_json` is an unstable, opaque
  format: paths are collected from path-ish keys plus path-looking tokens in
  command strings — best-effort, not contractual. A brand-new tool payload
  shape may yield partial edges.
- **CLI sessions only (M1).** GUI sessions (`acp-messages/*.db`) and
  `state.vscdb` are planned for M2.
- **Not a code index.** Nodes are files *the agent touched*, not repo
  contents; no symbol/AST knowledge.
- **Read-only by design** on Devin stores; `graph.db` is the only thing it
  writes.

## Development

```bash
pip install -e ".[dev]"
python -m pytest
```

Fixtures are generated at test time by `devin_internals.fixtures` (real v17
DDL, synthetic rows) — no binary fixtures are committed. See
[docs/SPEC.md](docs/SPEC.md) for the graph model and
[STATUS.md](STATUS.md) for the roadmap.

## License

MIT — see [LICENSE](LICENSE).
