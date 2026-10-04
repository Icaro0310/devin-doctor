"""Offline-core guard: the core must not open sockets.

Release checklist item: "no-network core test (CI): fails if the core
opens a socket". An autouse fixture monkeypatches ``socket.socket.connect``,
``socket.socket.connect_ex`` and ``socket.create_connection`` to raise
``OfflineCoreError`` for the duration of every test in this file, then the
tests run the repo's core operations end to end. This is a guard, not a
mock: any in-process network access fails the suite.

Intentional online paths are excluded by design: none exist in the core —
``index``/``query`` are read-only on local SQLite stores. Only in-process
sockets are blocked here.

Opt-out: mark a test ``@pytest.mark.network`` to run it without the socket
block (reserved for tests that intentionally exercise the network).

Run with:
``PYTHONPATH=src:../devin-internals-spec/src python -m pytest tests/test_offline_core.py``
(this repo imports ``devin_internals`` from the sibling checkout).
"""

from __future__ import annotations

import json
import socket

import pytest

from conftest import add_acp_db, add_session, msg
from devin_search.cli import main


class OfflineCoreError(RuntimeError):
    """Raised when core code tries to open a network connection."""


def _offline_fail(*args, **kwargs):
    raise OfflineCoreError("core opened a socket during the offline-core test")


@pytest.fixture(autouse=True)
def _block_sockets(request, monkeypatch):
    """Block all outbound sockets; opt out with ``@pytest.mark.network``."""
    if request.node.get_closest_marker("network"):
        return
    monkeypatch.setattr(socket.socket, "connect", _offline_fail)
    monkeypatch.setattr(socket.socket, "connect_ex", _offline_fail)
    monkeypatch.setattr(socket, "create_connection", _offline_fail)


def test_socket_block_is_active():
    """Sanity check: the guard itself raises on any connect attempt."""
    with pytest.raises(OfflineCoreError):
        socket.create_connection(("127.0.0.1", 1), timeout=0.01)
    with pytest.raises(OfflineCoreError):
        socket.socket().connect(("127.0.0.1", 1))


def test_index_then_query_offline(db_path, acp_dir, tmp_path, capsys):
    """Index a synthetic fixture then query it — all offline."""
    add_session(
        db_path,
        "cli-sess",
        messages=[msg("user", "remember the flibberty gibbet flag")],
    )
    add_acp_db(acp_dir, "gui", "gui-9", [("user", {"text": "nothing here"})])
    idx = tmp_path / "search.db"

    rc = main([
        "index",
        "--sessions-db", str(db_path),
        "--acp-dir", str(acp_dir),
        "--index", str(idx),
    ])
    assert rc == 0
    assert "indexed" in capsys.readouterr().out

    rc = main(["query", "flibberty", "--index", str(idx), "--json"])
    assert rc == 0
    hits = json.loads(capsys.readouterr().out)
    assert hits, "query should find the indexed message"
