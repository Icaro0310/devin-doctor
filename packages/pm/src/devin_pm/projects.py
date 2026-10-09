"""Group sessions into projects.

A *project* is the set of sessions that share a ``working_directory`` —
the basename of that directory is the project name. Grouping keys come
from :func:`devin_pm.paths.normalize_path` (PM-3): separators and
trailing slashes, ``C:\\x`` ⇄ ``/c/x`` drive equivalence (drive-rooted
paths fold case — the Windows filesystem is case-insensitive), and WSL
UNC prefixes. POSIX case is preserved — ``/home/u/Foo`` and
``/home/u/foo`` stay distinct. Display keeps the original path.

GUI sessions loaded from ``state.vscdb`` (:class:`GuiSession`, PM-1)
group by their workspace the same way and surface with ``status`` /
``source`` = ``"gui"``.
"""

from __future__ import annotations

import json
import os
import re
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from devin_internals.parsers import Session, SessionsStore

from devin_pm.paths import normalize_path
from devin_pm.vscdb import GuiSession

ENV_SESSIONS_DB = "DEVIN_PM_SESSIONS_DB"

_COST_KEY_RE = re.compile(r"(cost|credit|usd|amount|spent)", re.IGNORECASE)


def default_sessions_db() -> Path:
    """Locate Devin's ``sessions.db`` for the current platform.

    Order: ``DEVIN_PM_SESSIONS_DB`` env var → first existing platform
    candidate → the primary platform default (``%APPDATA%`` on Windows,
    ``$XDG_DATA_HOME`` on Linux, Application Support on macOS). Linux
    candidates follow the ecosystem convention — data dir, then config
    dir, then home — the same multi-root order ``devin_history.paths``
    and ``devin_pm.vscdb`` apply.
    """
    env = os.environ.get(ENV_SESSIONS_DB)
    if env:
        return Path(env).expanduser()
    if sys.platform == "win32":
        base = os.environ.get("APPDATA")
        roots = [Path(base) if base else Path.home() / "AppData" / "Roaming"]
    elif sys.platform == "darwin":
        roots = [Path.home() / "Library" / "Application Support"]
    else:
        roots = [
            Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")),
            Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")),
            Path.home(),
        ]
    candidates = [
        root / "devin" / "cli" / "sessions.db" for root in dict.fromkeys(roots)
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return candidates[0]


def load_sessions(db_path: str | Path) -> list[Session]:
    """Read every session from a ``sessions.db`` (read-only)."""
    with SessionsStore(db_path) as store:
        return store.sessions()


def _wd_key(working_directory: str) -> str:
    return working_directory.replace("\\", "/").rstrip("/")


def project_name(working_directory: str) -> str:
    """Project name = basename of the working directory."""
    parts = [p for p in _wd_key(working_directory).split("/") if p]
    return parts[-1] if parts else "?"


def extract_cost(cogs_json: str | None) -> float | None:
    """Best-effort cost extraction from a session's ``cogs_json``.

    ``cogs_json`` is an *unstable* payload (see devin-internals-spec
    SCHEMA.md): its inner shape is not documented, so this walks the JSON
    looking for numeric values under keys that look cost-ish
    (``cost*``, ``*usd``, ``credits*``, ``amount``, ``spent``). Returns
    ``None`` when nothing recognizable is found — ``None`` means "unknown",
    not "free".
    """
    if not cogs_json:
        return None
    try:
        data = json.loads(cogs_json)
    except (TypeError, json.JSONDecodeError):
        return None
    values: list[float] = []
    _collect_cost(data, values)
    return sum(values) if values else None


def _collect_cost(obj: object, out: list[float]) -> None:
    """Collect every numeric value under a cost-ish key."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            if isinstance(key, str) and _COST_KEY_RE.search(key):
                if isinstance(value, (int, float)):
                    out.append(float(value))
                elif isinstance(value, str):
                    try:
                        out.append(float(value))
                    except ValueError:
                        pass
                else:
                    _collect_cost(value, out)
            else:
                _collect_cost(value, out)
    elif isinstance(obj, list):
        for item in obj:
            _collect_cost(item, out)


@dataclass(frozen=True)
class Project:
    """All sessions sharing one working directory."""

    name: str
    working_directory: str
    sessions: tuple[Session | GuiSession, ...]

    @property
    def session_count(self) -> int:
        return len(self.sessions)

    @property
    def session_ids(self) -> list[str]:
        return [s.id for s in self.sessions]

    @property
    def last_activity_at(self) -> int:
        return max(s.last_activity_at for s in self.sessions)

    @property
    def status_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for s in self.sessions:
            counts[s.status] = counts.get(s.status, 0) + 1
        return counts

    @property
    def gui_session_count(self) -> int:
        """How many member sessions came from ``state.vscdb`` (PM-1)."""
        return sum(
            1 for s in self.sessions
            if getattr(s, "source", "cli") == "gui"
        )

    @property
    def cost(self) -> float | None:
        """Sum of extractable session costs; ``None`` if none found."""
        values = [c for c in (extract_cost(s.cogs_json) for s in self.sessions) if c is not None]
        return sum(values) if values else None


def group_sessions(sessions: Iterable[Session | GuiSession]) -> list[Project]:
    """Group sessions by (normalized) ``working_directory``.

    The grouping key is :func:`normalize_path` — Windows, MSYS/Cygwin and
    WSL-UNC spellings of one directory fold together. Returns projects
    sorted by last activity, most recent first.
    """
    groups: dict[str, list[Session | GuiSession]] = {}
    for session in sessions:
        groups.setdefault(
            normalize_path(session.working_directory), []
        ).append(session)

    projects = [
        Project(
            name=project_name(members[0].working_directory),
            working_directory=_wd_key(members[0].working_directory),
            sessions=tuple(
                sorted(members, key=lambda s: s.last_activity_at, reverse=True)
            ),
        )
        for members in groups.values()
    ]
    return sorted(projects, key=lambda p: p.last_activity_at, reverse=True)


def find_project(projects: Iterable[Project], name: str) -> Project | None:
    """Find a project by name (case-insensitive)."""
    for project in projects:
        if project.name.lower() == name.lower():
            return project
    return None
