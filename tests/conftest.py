"""Shared fixtures: a synthetic ``sessions.db`` with crafted session rows.

The DDL + migration ledger come from ``devin_internals.fixtures``; every row
inserted on top is synthetic and deterministic — no real session content.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pytest
from devin_internals.fixtures import create_sessions_db

BASE_TS_MS = 1_780_000_000_000


def insert_session(
    db_path: str | Path,
    *,
    sid: str,
    working_directory: str,
    title: str | None = None,
    created_at: int = BASE_TS_MS,
    last_activity_at: int | None = None,
    hidden: int = 0,
    cogs_json: str | None = None,
    model: str = "fixture-model",
) -> str:
    con = sqlite3.connect(str(db_path))
    try:
        con.execute(
            "INSERT INTO sessions(id, working_directory, backend_type, model,"
            " agent_mode, created_at, last_activity_at, title, hidden,"
            " cogs_json) VALUES (?, ?, 'fixture-backend', ?, 'fixture-mode',"
            " ?, ?, ?, ?, ?)",
            (
                sid,
                working_directory,
                model,
                created_at,
                last_activity_at
                if last_activity_at is not None
                else created_at + 120_000,
                title,
                hidden,
                cogs_json,
            ),
        )
        con.commit()
    finally:
        con.close()
    return sid


@pytest.fixture
def workdir(tmp_path: Path) -> Path:
    """Tmp dir containing two real project directories, alpha/ and beta/."""
    (tmp_path / "alpha").mkdir()
    (tmp_path / "beta").mkdir()
    return tmp_path


@pytest.fixture
def sessions_db(workdir: Path) -> Path:
    """Synthetic sessions.db: 5 crafted sessions across projects alpha + beta.

    - alpha: 3 sessions (one hidden, one ``milestone:`` title, one with a
      trailing separator in ``working_directory`` to exercise normalization,
      ``cogs_json`` cost fields summing to 0.75)
    - beta: 2 sessions (one ``milestone:`` title, still active → pending)
    """
    db = create_sessions_db(workdir / "sessions.db", n_sessions=0)
    alpha = str(workdir / "alpha")
    beta = str(workdir / "beta")
    insert_session(
        db,
        sid="a-1",
        working_directory=alpha,
        title="alpha: initial setup",
        created_at=BASE_TS_MS,
        cogs_json='{"cost": 0.25}',
    )
    insert_session(
        db,
        sid="a-2",
        working_directory=alpha + os.sep,
        title="milestone: Alpha scaffold",
        created_at=BASE_TS_MS + 3_600_000,
        hidden=1,
        cogs_json='{"totals": {"cost_usd": 0.50}}',
    )
    insert_session(
        db,
        sid="a-3",
        working_directory=alpha,
        title="alpha: fix failing tests",
        created_at=BASE_TS_MS + 7_200_000,
    )
    insert_session(
        db,
        sid="b-1",
        working_directory=beta,
        title="milestone: Beta MVP",
        created_at=BASE_TS_MS + 10_800_000,
    )
    insert_session(
        db,
        sid="b-2",
        working_directory=beta,
        title="beta: write docs",
        created_at=BASE_TS_MS + 14_400_000,
    )
    return db
