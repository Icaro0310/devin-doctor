"""GUI sessions from Devin Desktop's ``state.vscdb`` (PM-1).

``state.vscdb`` is the Electron ``ItemTable`` key/value store under
``User/globalStorage/`` of the Devin config dir. GUI sessions have no
transcript — the only record is a session→workspace binding under keys of
the form ``windsurfSpace.sessionWorkspace/<backend>/<slug>`` holding JSON
``{workspaceId, label, folders[], lastUpdated}``.

Each binding becomes a :class:`GuiSession`, a ``Session``-shaped record
(``id``/``working_directory``/``title``/``status``/… properties) so it
groups alongside ``sessions.db`` rows; ``source = "gui"`` and
``status = "gui"`` mark it in output. Coverage is best-effort: unknown or
malformed keys are skipped, never fatal, and the store is opened
read-only via ``devin_internals``' ``StateVscdbStore`` (``mode=ro``).
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

from devin_internals.parsers import StateVscdbStore

ENV_STATE_VSCDB = "DEVIN_PM_STATE_VSCDB"
SESSION_WS_PREFIX = "windsurfSpace.sessionWorkspace/"
VSCDB_RELPATH = ("User", "globalStorage", "state.vscdb")


def _state_vscdb_candidates() -> list[Path]:
    """``<config>/Devin|devin/User/globalStorage/state.vscdb`` per platform."""
    if sys.platform == "win32":
        base = os.environ.get("APPDATA")
        roots = [Path(base)] if base else [Path.home() / "AppData" / "Roaming"]
    elif sys.platform == "darwin":
        roots = [Path.home() / "Library" / "Application Support"]
    else:
        roots = [
            Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")),
            Path.home(),
        ]
    return [
        root.joinpath(name, *VSCDB_RELPATH)
        for root in dict.fromkeys(roots)
        for name in ("Devin", "devin")
    ]


def default_state_vscdb() -> Path | None:
    """Locate the GUI ``state.vscdb``; ``None`` when no candidate exists.

    Order: ``DEVIN_PM_STATE_VSCDB`` env var → first existing platform
    candidate.
    """
    env = os.environ.get(ENV_STATE_VSCDB)
    if env:
        return Path(env).expanduser()
    for candidate in _state_vscdb_candidates():
        if candidate.is_file():
            return candidate
    return None


def _json_dict(raw: Any) -> dict:
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _as_str(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _as_ms(value: Any) -> int | None:
    """``lastUpdated`` → epoch ms when it looks numeric; else ``None``."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


@dataclass(frozen=True)
class GuiSession:
    """A GUI session↔workspace binding; there is no transcript behind it.

    The properties mirror :class:`devin_internals.parsers.Session` so
    grouping, reports and milestones treat it uniformly. Grouping uses
    ``workspaceId`` (falling back to the first ``folders[]`` entry, then
    ``label``) as the working directory; ``status`` is ``"gui"``.
    """

    slug: str
    backend: str
    workspace_id: str | None
    label: str | None
    folders: tuple[str, ...]
    last_updated: int | None

    source: ClassVar[str] = "gui"

    @property
    def id(self) -> str:
        return self.slug

    @property
    def working_directory(self) -> str:
        return (
            self.workspace_id
            or (self.folders[0] if self.folders else None)
            or self.label
            or ""
        )

    @property
    def title(self) -> str | None:
        return self.label

    @property
    def created_at(self) -> int:
        return self.last_updated or 0

    @property
    def last_activity_at(self) -> int:
        return self.last_updated or 0

    @property
    def status(self) -> str:
        return "gui"

    @property
    def hidden(self) -> bool:
        return False

    @property
    def backend_type(self) -> str:
        return self.backend

    @property
    def cogs_json(self) -> None:
        return None


def load_gui_sessions(vscdb_path: str | Path) -> list[GuiSession]:
    """GUI session→workspace bindings from a ``state.vscdb`` (read-only)."""
    with StateVscdbStore(vscdb_path) as store:
        rows = store.list_prefix(SESSION_WS_PREFIX)
    sessions: list[GuiSession] = []
    for key in sorted(rows):
        backend, sep, slug = key[len(SESSION_WS_PREFIX):].rpartition("/")
        if not sep or not slug:
            continue
        data = _json_dict(rows[key])
        sessions.append(
            GuiSession(
                slug=slug,
                backend=backend,
                workspace_id=_as_str(data.get("workspaceId")),
                label=_as_str(data.get("label")),
                folders=tuple(
                    f for f in (data.get("folders") or [])
                    if isinstance(f, str)
                ),
                last_updated=_as_ms(data.get("lastUpdated")),
            )
        )
    return sessions
