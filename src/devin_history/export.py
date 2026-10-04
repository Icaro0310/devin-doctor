"""Export ``sessions.db`` to one file per session plus an index.

Idempotent: the session's ``last_activity`` marker is embedded in each note's
frontmatter (md) or top-level field (json); a rerun skips files whose marker
already matches. Never writes to the source database — the caller hands in a
read-only ``SessionsStore``.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from devin_history import identity
from devin_history.format import (
    project_name,
    render_index_json,
    render_index_md,
    render_session_md,
    session_to_dict,
)
from devin_history.messages import parse_nodes
from devin_history.times import fmt_ts

MIN_USEFUL_NODES = 2
FORMATS = ("md", "json")

_MARKER_MD = re.compile(r"^last_activity:\s*(\d+)", re.M)


@dataclass(frozen=True)
class IndexEntry:
    date: str
    filename: str
    title: str
    project: str


@dataclass
class ExportResult:
    out_dir: Path
    format: str
    written: list[str] = field(default_factory=list)
    skipped_unchanged: list[str] = field(default_factory=list)
    skipped_empty: list[str] = field(default_factory=list)
    index_entries: list[IndexEntry] = field(default_factory=list)


def _exported_marker(path: Path, fmt: str) -> int | None:
    """Stored ``last_activity`` of a previously written note, if readable."""
    if not path.exists():
        return None
    try:
        if fmt == "md":
            head = path.read_text(encoding="utf-8")[:800]
            m = _MARKER_MD.search(head)
            return int(m.group(1)) if m else -1
        data = json.loads(path.read_text(encoding="utf-8"))
        return int(data.get("last_activity", -1))
    except (OSError, ValueError):
        return -1


def _write_if_changed(path: Path, text: str) -> bool:
    try:
        if path.read_text(encoding="utf-8") == text:
            return False
    except OSError:
        pass
    path.write_text(text, encoding="utf-8")
    return True


def export_sessions(
    store,
    out_dir: str | Path,
    *,
    fmt: str = "md",
    force: bool = False,
    dry_run: bool = False,
) -> ExportResult:
    """Export every useful session in ``store`` to ``out_dir``.

    ``fmt`` is ``md`` (Obsidian notes) or ``json`` (searchable dump). Sessions
    with no user messages or fewer than ``MIN_USEFUL_NODES`` nodes are skipped.
    """
    if fmt not in FORMATS:
        raise ValueError(f"unknown format {fmt!r} (expected one of {FORMATS})")
    out_dir = Path(out_dir)
    result = ExportResult(out_dir=out_dir, format=fmt)
    if not dry_run:
        out_dir.mkdir(parents=True, exist_ok=True)

    prov = identity.provenance()
    sessions = sorted(store.sessions(), key=lambda s: s.created_at)
    for s in sessions:
        nodes = store.message_nodes(s.id)
        messages = parse_nodes(nodes)
        user_msgs = sum(1 for m in messages if m.role == "user")
        if user_msgs == 0 or len(nodes) < MIN_USEFUL_NODES:
            result.skipped_empty.append(s.id)
            continue

        date = fmt_ts(s.created_at, "%Y-%m-%d")
        filename = f"{date}_{s.id}.{fmt}"
        fpath = out_dir / filename

        if not force and _exported_marker(fpath, fmt) == s.last_activity_at:
            result.skipped_unchanged.append(s.id)
        else:
            if fmt == "md":
                text = render_session_md(s, messages, prov)
            else:
                text = json.dumps(
                    session_to_dict(s, messages, store.tool_call_state(s.id), prov),
                    ensure_ascii=False,
                    indent=2,
                ) + "\n"
            if not dry_run:
                _write_if_changed(fpath, text)
            result.written.append(filename)

        result.index_entries.append(
            IndexEntry(
                date=date,
                filename=filename,
                title=(s.title or "Untitled").strip(),
                project=project_name(s.working_directory),
            )
        )

    if not dry_run:
        index = (
            render_index_md(result.index_entries)
            if fmt == "md"
            else render_index_json(result.index_entries, prov)
        )
        _write_if_changed(out_dir / f"index.{fmt}", index)

    return result
