"""Optional links from search hits to devin-history export notes.

``devin-history export`` writes one note per session named
``<YYYY-MM-DD>_<session-id>.md`` (or ``.json``) in its export directory.
The index does not store the session's ``created_at``, so matching is by
the ``_<session-id>.<ext>`` filename suffix. Everything here is
best-effort: a missing directory or missing note produces no link and no
error.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Iterable

from devin_search.query import Hit

# Preferred note formats first — an export dir may hold both.
_NOTE_SUFFIXES = (".md", ".json")


def history_note(history_dir: str | Path, session_id: str) -> Path | None:
    """The exported note for ``session_id`` in ``history_dir``, or ``None``."""
    if not session_id:
        return None
    d = Path(history_dir).expanduser()
    if not d.is_dir():
        return None
    names = sorted(p.name for p in d.iterdir() if p.is_file())
    for ext in _NOTE_SUFFIXES:
        for name in names:
            if name.endswith(f"_{session_id}{ext}"):
                return d / name
    return None


def attach_history_notes(
    hits: Iterable[Hit], history_dir: str | Path
) -> list[Hit]:
    """Return hits with ``history_note`` set when the note file exists."""
    d = Path(history_dir).expanduser()
    if not d.is_dir():
        return list(hits)
    cache: dict[str, Path | None] = {}
    out: list[Hit] = []
    for h in hits:
        if h.session_id not in cache:
            cache[h.session_id] = history_note(d, h.session_id)
        note = cache[h.session_id]
        out.append(h if note is None else replace(h, history_note=str(note)))
    return out
