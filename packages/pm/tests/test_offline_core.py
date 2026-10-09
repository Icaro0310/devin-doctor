"""Offline-core guard: the core must not open sockets.

Release checklist item: "no-network core test (CI): fails if the core
opens a socket". An autouse fixture monkeypatches ``socket.socket.connect``,
``socket.socket.connect_ex`` and ``socket.create_connection`` to raise
``OfflineCoreError`` for the duration of every test in this file, then the
tests run the repo's core operations end to end. This is a guard, not a
mock: any in-process network access fails the suite.

Intentional online paths are excluded by design: none exist in the core —
status/report/milestones/registry are read-only rollups over local
sessions.db / state.vscdb stores. Only in-process sockets are blocked
here.

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
from devin_pm.cli import main


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


@pytest.fixture
def db_flag(sessions_db):
    return ["--sessions-db", str(sessions_db)]


def test_socket_block_is_active():
    """Sanity check: the guard itself raises on any connect attempt."""
    with pytest.raises(OfflineCoreError):
        socket.create_connection(("127.0.0.1", 1), timeout=0.01)
    with pytest.raises(OfflineCoreError):
        socket.socket().connect(("127.0.0.1", 1))


def test_status_report_registry_offline(db_flag, capsys):
    """status + report + registry over the conftest sessions.db, offline."""
    assert main(["status", *db_flag, "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    by_name = {p["name"]: p for p in data}
    assert by_name["alpha"]["sessions"] == 3

    assert main(["report", *db_flag, "--project", "alpha"]) == 0
    assert capsys.readouterr().out.strip()

    assert main(["registry", *db_flag]) == 0
    registry = json.loads(capsys.readouterr().out)
    assert registry["version"] == 1
    assert registry["totals"]["projects"] == 2
