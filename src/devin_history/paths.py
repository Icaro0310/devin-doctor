"""Default locations for Devin's local session stores.

Windows is the primary target (``%APPDATA%/devin/cli/sessions.db``); Linux and
macOS candidates are included so the CLI works there too.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_DIRNAME = "devin"
SESSIONS_DB_RELPATH = ("cli", "sessions.db")


def sessions_db_candidates() -> list[Path]:
    """Candidate paths for the CLI ``sessions.db``, in priority order."""
    if sys.platform == "win32" or os.name == "nt":
        roots = []
        appdata = os.environ.get("APPDATA")
        if appdata:
            roots.append(Path(appdata))
        roots.append(Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        roots = [Path.home() / "Library" / "Application Support"]
    else:
        roots = [
            Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config"),
            Path.home(),
        ]
    return [r.joinpath(APP_DIRNAME, *SESSIONS_DB_RELPATH) for r in roots]


def default_sessions_db() -> Path | None:
    """First existing candidate, or ``None`` when no store is present."""
    for candidate in sessions_db_candidates():
        if candidate.is_file():
            return candidate
    return None
