"""Check 2 — schema: version/shape detection per store.

``sessions.db`` is gated by :func:`devin_internals.detect_schema_version`
(ledger ``refinery_schema_history``); the ledger-less stores
(``acp-messages/*.db``, ``state.vscdb``) are gated on table shape by their
parsers.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from devin_internals import detect_schema_version
from devin_internals.parsers import AcpMessagesStore, StateVscdbStore
from devin_internals.schema import (
    LATEST_KNOWN_SCHEMA,
    MIN_SUPPORTED_SCHEMA,
    SchemaError,
    UnknownSchemaVersionError,
)

from devin_doctor.model import Context, Finding, Status
from devin_doctor.paths import locate_stores

CHECK_ID = "schema"

_UPDATE_FIX = (
    "Upgrade devin-doctor / devin-internals-spec — this store was written by "
    "a newer Devin than the spec knows about."
)


def _sessions_db_finding(path: Path) -> Finding:
    if not path.is_file():
        return Finding(
            CHECK_ID,
            Status.WARN,
            f"sessions.db missing — schema detection skipped ({path})",
        )
    try:
        info = detect_schema_version(path)
    except UnknownSchemaVersionError as exc:
        return Finding(
            CHECK_ID,
            Status.FAIL,
            f"sessions.db schema v{exc.version} — unknown (known range "
            f"{MIN_SUPPORTED_SCHEMA}..{LATEST_KNOWN_SCHEMA})",
            fix=_UPDATE_FIX,
        )
    except SchemaError as exc:
        return Finding(
            CHECK_ID,
            Status.FAIL,
            f"sessions.db schema detection failed: {exc}",
            fix="The file is missing the migration ledger — is it really a "
            "Devin sessions.db?",
        )
    except (sqlite3.Error, OSError) as exc:
        return Finding(
            CHECK_ID,
            Status.FAIL,
            f"sessions.db is not a readable database: {exc}",
            fix="File looks corrupt — restore from backup or reinstall Devin.",
        )
    version = info["schema_version"]
    if not info["supported"]:
        return Finding(
            CHECK_ID,
            Status.FAIL,
            f"sessions.db schema v{version} — known but unsupported "
            f"(supported: {MIN_SUPPORTED_SCHEMA}..{LATEST_KNOWN_SCHEMA})",
            fix=_UPDATE_FIX,
        )
    suffix = "latest known" if info["verified"] else "supported"
    return Finding(
        CHECK_ID, Status.PASS, f"sessions.db schema v{version} ({suffix})"
    )


def _acp_finding(acp_dir: Path, acp_dbs: tuple[Path, ...]) -> Finding:
    if not acp_dir.is_dir() or not acp_dbs:
        return Finding(
            CHECK_ID,
            Status.WARN,
            "acp-messages: nothing to check (dir missing or empty)",
        )
    bad: list[str] = []
    for p in acp_dbs:
        try:
            with AcpMessagesStore(p):
                pass
        except (SchemaError, sqlite3.Error, OSError):
            bad.append(p.name)
    if bad:
        shown = ", ".join(bad[:3]) + (" …" if len(bad) > 3 else "")
        return Finding(
            CHECK_ID,
            Status.FAIL,
            f"acp-messages: {len(bad)}/{len(acp_dbs)} db(s) with unrecognized "
            f"layout ({shown})",
            fix="These files lack the meta+messages tables — possibly written "
            "by a newer Devin or corrupted.",
        )
    return Finding(
        CHECK_ID,
        Status.PASS,
        f"acp-messages: {len(acp_dbs)}/{len(acp_dbs)} db(s) have the "
        "recognized meta+messages layout",
    )


def _state_vscdb_finding(path: Path) -> Finding:
    if not path.is_file():
        return Finding(
            CHECK_ID,
            Status.WARN,
            f"state.vscdb missing — shape check skipped ({path})",
        )
    try:
        with StateVscdbStore(path):
            pass
    except (SchemaError, sqlite3.Error, OSError) as exc:
        return Finding(
            CHECK_ID,
            Status.FAIL,
            f"state.vscdb has an unrecognized layout: {exc}",
            fix="Expected a VS Code-style ItemTable — file may be corrupt or "
            "from an unknown version.",
        )
    return Finding(
        CHECK_ID, Status.PASS, "state.vscdb layout recognized (ItemTable)"
    )


def run(ctx: Context) -> list[Finding]:
    stores = locate_stores(ctx.data_dir)
    return [
        _sessions_db_finding(stores.sessions_db),
        _acp_finding(stores.acp_dir, stores.acp_dbs),
        _state_vscdb_finding(stores.state_vscdb),
    ]
