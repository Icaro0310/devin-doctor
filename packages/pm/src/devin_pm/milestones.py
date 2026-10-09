"""Milestones per project.

Two sources, merged:

- **Session titles** — a session titled ``milestone: <name>`` marks a
  milestone in that project's working directory. A *hidden* (archived)
  session counts as **done**; an active one counts as pending. Archiving
  the session is how you mark the milestone complete.
- **``milestones.json``** in the project root — manual entries::

      {"milestones": [{"name": "M1", "done": true}, "M2"]}

  Accepts a top-level list too. Strings mean pending. File entries win
  over session-detected ones on name collision (case-insensitive).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from devin_internals.parsers import Session
from devin_pm.projects import Project

MILESTONE_TITLE_RE = re.compile(r"^\s*milestone\s*:\s*(?P<name>.+?)\s*$", re.IGNORECASE)
MILESTONES_FILENAME = "milestones.json"


class MilestonesError(RuntimeError):
    """``milestones.json`` exists but is malformed."""


@dataclass(frozen=True)
class Milestone:
    name: str
    done: bool
    session_id: str | None = None
    source: str = "file"  # "file" | "session"


def detect_milestones(sessions: Iterable[Session]) -> list[Milestone]:
    """Milestones declared via ``milestone: <name>`` session titles."""
    found: list[Milestone] = []
    for session in sessions:
        if not session.title:
            continue
        match = MILESTONE_TITLE_RE.match(session.title)
        if match:
            found.append(
                Milestone(
                    name=match.group("name"),
                    done=session.hidden,
                    session_id=session.id,
                    source="session",
                )
            )
    return found


def milestones_path(project: Project) -> Path:
    """``milestones.json`` at the root of the project's working directory."""
    return Path(project.working_directory) / MILESTONES_FILENAME


def _entry_to_milestone(entry: object) -> Milestone:
    if isinstance(entry, str):
        return Milestone(name=entry, done=False)
    if isinstance(entry, dict) and "name" in entry:
        return Milestone(
            name=str(entry["name"]),
            done=bool(entry.get("done", False)),
            session_id=entry.get("session_id"),
        )
    raise MilestonesError(
        f"invalid milestone entry: {entry!r} (expected string or "
        '{"name": ..., "done": ...})'
    )


def load_milestones(path: str | Path) -> list[Milestone]:
    """Read a ``milestones.json``; ``[]`` when the file does not exist."""
    path = Path(path)
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MilestonesError(f"{path}: invalid JSON — {exc}") from exc

    entries = data.get("milestones") if isinstance(data, dict) else data
    if not isinstance(entries, list):
        raise MilestonesError(
            f"{path}: expected a list or an object with a 'milestones' list"
        )
    return [_entry_to_milestone(e) for e in entries]


def collect_milestones(project: Project) -> list[Milestone]:
    """File entries first, then session-detected; dedup by name."""
    merged: dict[str, Milestone] = {}
    for m in load_milestones(milestones_path(project)):
        merged.setdefault(m.name.lower(), m)
    for m in detect_milestones(project.sessions):
        merged.setdefault(m.name.lower(), m)
    return list(merged.values())


def done_fraction(milestones: Iterable[Milestone]) -> tuple[int, int, float]:
    """``(done, total, percent)`` — percent is 0.0 when there are none."""
    ms = list(milestones)
    total = len(ms)
    done = sum(1 for m in ms if m.done)
    return done, total, (done / total * 100.0) if total else 0.0
