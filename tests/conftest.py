"""Fixtures — generated synthetically via devin_internals.fixtures.

No real Devin data is ever touched: every test database is produced by the
deterministic generator (DDL is real, rows are synthetic).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from devin_internals.fixtures import (
    _BASE_TS_MS,
    create_devin_data_dir,
    create_sessions_db,
)

from devin_doctor.model import Context


@pytest.fixture(autouse=True)
def _offline_updates(monkeypatch):
    # the updates check talks to the network and inspects real PATH installs;
    # pin it offline so full-scan tests stay hermetic on any machine.
    # tests for the check itself delete the variable.
    monkeypatch.setenv("DEVIN_DOCTOR_OFFLINE", "1")


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    """A healthy synthetic Devin data dir (schema v17, 3 sessions, 2 acp DBs)."""
    root = tmp_path / "devin"
    create_devin_data_dir(root)
    (root / "credentials.toml").write_text(
        '[auth]\ntoken = "fixture-token"\n', encoding="utf-8"
    )
    return root


@pytest.fixture
def ctx(data_dir: Path, tmp_path: Path) -> Context:
    """Context pointed at the healthy fixture; ``now_ms`` pinned just after
    the fixture's timestamps so nothing reads as stale by accident."""
    return Context(data_dir=data_dir, cwd=tmp_path, now_ms=_BASE_TS_MS + 10**9)


@pytest.fixture
def broken_data_dir(tmp_path: Path) -> Path:
    """Broken variant: no acp-messages dir, unknown schema_version on
    sessions.db, no state.vscdb, no credentials.toml."""
    root = tmp_path / "devin-broken"
    create_sessions_db(root / "cli" / "sessions.db", schema_version=99)
    return root


@pytest.fixture
def broken_ctx(broken_data_dir: Path, tmp_path: Path) -> Context:
    return Context(data_dir=broken_data_dir, cwd=tmp_path)


def lock_db_exclusively(path: Path) -> sqlite3.Connection:
    """Hold an EXCLUSIVE lock on ``path`` (rollback-journal mode) so readers
    hit SQLITE_BUSY. Caller must keep the returned connection open."""
    con = sqlite3.connect(path)
    con.execute("PRAGMA journal_mode=DELETE")
    con.execute("BEGIN EXCLUSIVE")
    con.execute(
        "INSERT INTO app_state(key, value) VALUES ('fixture.lock', '1')"
    )
    return con
