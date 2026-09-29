"""Default locations for Devin's local session stores and the search index.

Windows is the primary target (``%APPDATA%/devin/...``); Linux and macOS
candidates are included so the CLI works there too. The index lives under a
separate ``devin-search`` app dir — it is the only file this tool writes.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_DIRNAME = "devin"
INDEX_DIRNAME = "devin-search"
INDEX_FILENAME = "search.db"
SESSIONS_DB_RELPATH = ("cli", "sessions.db")
ACP_MESSAGES_RELPATH = ("User", "acp-messages")


def _app_roots() -> list[Path]:
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
    return roots


def sessions_db_candidates() -> list[Path]:
    """Candidate paths for the CLI ``sessions.db``, in priority order."""
    return [
        r.joinpath(APP_DIRNAME, *SESSIONS_DB_RELPATH) for r in _app_roots()
    ]


def acp_dir_candidates() -> list[Path]:
    """Candidate paths for the GUI ``acp-messages`` directory."""
    return [
        r.joinpath(APP_DIRNAME, *ACP_MESSAGES_RELPATH) for r in _app_roots()
    ]


def default_sessions_db() -> Path | None:
    """First existing ``sessions.db`` candidate, or ``None``."""
    for candidate in sessions_db_candidates():
        if candidate.is_file():
            return candidate
    return None


def default_acp_dir() -> Path | None:
    """First existing ``acp-messages`` directory candidate, or ``None``."""
    for candidate in acp_dir_candidates():
        if candidate.is_dir():
            return candidate
    return None


def default_index_path() -> Path:
    """Where ``search.db`` lives when ``--index`` is not given."""
    return _app_roots()[0] / INDEX_DIRNAME / INDEX_FILENAME
