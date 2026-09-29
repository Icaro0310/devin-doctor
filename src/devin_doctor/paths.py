"""Locations of Devin's local stores and config files.

Windows: ``%APPDATA%/devin`` · macOS: ``~/Library/Application Support/devin`` ·
Linux/other: ``~/.config/devin``. Inside the data dir the layout is::

    cli/sessions.db                    CLI session store (schema-ledgered)
    cli/session_locks/*.lock           per-session lock files
    User/acp-messages/<uuid>.db        per-session GUI message logs
    User/globalStorage/state.vscdb     VS Code-style key/value store
    credentials.toml                   auth material (never print values)
    config.json                        user-level config (JSONC)
    mcp_config.json                    user-level MCP servers (JSONC)
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path


def default_data_dir() -> Path:
    if sys.platform.startswith("win"):
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / "devin"
        return Path.home() / "AppData" / "Roaming" / "devin"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "devin"
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "devin"


def sessions_db_path(root: Path) -> Path:
    return root / "cli" / "sessions.db"


def acp_messages_dir(root: Path) -> Path:
    return root / "User" / "acp-messages"


def state_vscdb_path(root: Path) -> Path:
    return root / "User" / "globalStorage" / "state.vscdb"


def credentials_path(root: Path) -> Path:
    return root / "credentials.toml"


def user_config_path(root: Path) -> Path:
    return root / "config.json"


def user_mcp_config_path(root: Path) -> Path:
    return root / "mcp_config.json"


def session_locks_dir(root: Path) -> Path:
    return root / "cli" / "session_locks"


@dataclass(frozen=True)
class StorePaths:
    """Everything the checks need to know about where stores live."""

    sessions_db: Path
    acp_dir: Path
    acp_dbs: tuple[Path, ...]
    state_vscdb: Path

    def all_db_files(self) -> list[Path]:
        files = [self.sessions_db, *self.acp_dbs, self.state_vscdb]
        return [p for p in files if p.is_file()]


def locate_stores(root: Path) -> StorePaths:
    acp_dir = acp_messages_dir(root)
    acp_dbs = (
        tuple(sorted(acp_dir.glob("*.db"))) if acp_dir.is_dir() else ()
    )
    return StorePaths(
        sessions_db=sessions_db_path(root),
        acp_dir=acp_dir,
        acp_dbs=acp_dbs,
        state_vscdb=state_vscdb_path(root),
    )


def human_size(n: int) -> str:
    value = float(n)
    for unit in ("B", "KiB", "MiB", "GiB"):
        if value < 1024 or unit == "GiB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{n} B"
