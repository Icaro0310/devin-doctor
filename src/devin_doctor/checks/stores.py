"""Check 1 — stores: locate the three Devin stores and report
present/missing, on-disk size and row counts.

Row counts come from the read-only parsers in ``devin_internals``; a store
that exists but cannot be opened is reported FAIL here and diagnosed further
by the ``schema`` check.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from devin_internals.parsers import (
    AcpMessagesStore,
    SessionsStore,
    StateVscdbStore,
)
from devin_internals.schema import SchemaError

from devin_doctor.model import Context, Finding, Status
from devin_doctor.paths import human_size, locate_stores

CHECK_ID = "stores"


def _sessions_db_finding(path: Path) -> Finding:
    if not path.is_file():
        return Finding(
            CHECK_ID,
            Status.FAIL,
            f"sessions.db missing ({path})",
            fix="Is Devin installed? If your data lives elsewhere, pass --data-dir.",
        )
    size = path.stat().st_size
    try:
        with SessionsStore(path) as store:
            counts = store.counts()
    except (SchemaError, OSError, sqlite3.Error) as exc:
        return Finding(
            CHECK_ID,
            Status.FAIL,
            f"sessions.db present ({human_size(size)}) but unreadable: {exc}",
            fix="The file does not look like a Devin sessions.db — see the schema check.",
        )
    return Finding(
        CHECK_ID,
        Status.PASS,
        f"sessions.db present — {human_size(size)}, "
        f"{counts['sessions']} sessions, {counts['message_nodes']} message_nodes",
    )


def _acp_finding(acp_dir: Path, acp_dbs: tuple[Path, ...]) -> Finding:
    if not acp_dir.is_dir():
        return Finding(
            CHECK_ID,
            Status.WARN,
            f"acp-messages dir missing ({acp_dir})",
            fix="Devin Desktop has probably never run a session here — safe to "
            "ignore if you only use the CLI.",
        )
    if not acp_dbs:
        return Finding(
            CHECK_ID,
            Status.PASS,
            "acp-messages dir present, 0 db files",
        )
    total = sum(p.stat().st_size for p in acp_dbs)
    unreadable: list[str] = []
    for p in acp_dbs:
        try:
            with AcpMessagesStore(p):
                pass
        except (SchemaError, OSError, sqlite3.Error):
            unreadable.append(p.name)
    if unreadable:
        return Finding(
            CHECK_ID,
            Status.FAIL,
            f"acp-messages: {len(acp_dbs)} db(s), {human_size(total)} — "
            f"{len(unreadable)} unreadable ({', '.join(unreadable[:3])})",
            fix="Unrecognized acp-messages layout — see the schema check.",
        )
    return Finding(
        CHECK_ID,
        Status.PASS,
        f"acp-messages: {len(acp_dbs)} db(s), {human_size(total)} total",
    )


def _state_vscdb_finding(path: Path) -> Finding:
    if not path.is_file():
        return Finding(
            CHECK_ID,
            Status.WARN,
            f"state.vscdb missing ({path})",
            fix="Desktop UI state store not found — Devin Desktop may never "
            "have launched here.",
        )
    size = path.stat().st_size
    try:
        with StateVscdbStore(path) as store:
            n_keys = store.counts()["ItemTable"]
            n_ws = len(store.list_prefix())
    except (SchemaError, OSError, sqlite3.Error) as exc:
        return Finding(
            CHECK_ID,
            Status.FAIL,
            f"state.vscdb present ({human_size(size)}) but unreadable: {exc}",
            fix="The file does not look like a state.vscdb — see the schema check.",
        )
    return Finding(
        CHECK_ID,
        Status.PASS,
        f"state.vscdb present — {human_size(size)}, {n_keys} keys "
        f"({n_ws} windsurfSpace.*)",
    )


def run(ctx: Context) -> list[Finding]:
    if not ctx.data_dir.is_dir():
        return [
            Finding(
                CHECK_ID,
                Status.FAIL,
                f"Devin data dir not found: {ctx.data_dir}",
                fix="Install Devin, or pass --data-dir pointing at it.",
            )
        ]
    stores = locate_stores(ctx.data_dir)
    return [
        _sessions_db_finding(stores.sessions_db),
        _acp_finding(stores.acp_dir, stores.acp_dbs),
        _state_vscdb_finding(stores.state_vscdb),
    ]
