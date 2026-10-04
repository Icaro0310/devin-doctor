import json
import sqlite3
from pathlib import Path

import pytest
from devin_internals.fixtures import create_sessions_db
from devin_internals.parsers import SessionsStore

BASE_MS = 1_780_000_000_000

ITEMTABLE_DDL = (
    "CREATE TABLE ItemTable (key TEXT UNIQUE ON CONFLICT REPLACE, value BLOB)"
)


@pytest.fixture
def db_path(tmp_path):
    return create_sessions_db(tmp_path / "sessions.db")


@pytest.fixture
def store(db_path):
    with SessionsStore(db_path) as s:
        yield s


def create_vscdb(path, items):
    """Synthetic ``state.vscdb``: an ``ItemTable`` with ``items`` key/values."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    with con:
        con.execute(ITEMTABLE_DDL)
        con.executemany(
            "INSERT INTO ItemTable(key, value) VALUES (?, ?)",
            list(items.items()),
        )
    con.close()
    return path


def gui_items(**overrides):
    """Realistic ``windsurfSpace.*`` ItemTable contents for two GUI sessions."""
    items = {
        "windsurfSpace.sessionWorkspace/acp/canyon-newspaper": json.dumps({
            "workspaceId": "/work/alpha",
            "label": "Fix flaky test",
            "folders": ["/work/alpha", "/work/shared"],
            "lastUpdated": BASE_MS,
        }),
        "windsurfSpace.sessionWorkspace/ssh-remote/river-otter": json.dumps({
            "workspaceId": "/srv/beta",
            "label": "Deploy runbook",
            "folders": ["/srv/beta"],
            "lastUpdated": BASE_MS + 86_400_000,
        }),
        "windsurfSpace.sessionWorkspace/malformed": "{}",  # no slug → skip
        "windsurfSpace.sessionWorkspace/acp/broken-json": "not json{",
        "windsurfSpace.resourceToSpace": json.dumps({
            "space-1": [
                "vscode-cascade-editor:///cascade-acp/acp/canyon-newspaper"
            ],
        }),
        "windsurfSpace.metadata": json.dumps({
            "space-1": {"lastAccessed": BASE_MS + 5_000},
        }),
        "unrelated.key": json.dumps({"ignored": True}),
    }
    items.update(overrides)
    return items


@pytest.fixture
def vscdb_path(tmp_path):
    return create_vscdb(tmp_path / "state.vscdb", gui_items())


@pytest.fixture
def vstore(vscdb_path):
    from devin_internals.parsers import StateVscdbStore

    with StateVscdbStore(vscdb_path) as s:
        yield s


def msg(role, text, **extra):
    return {"role": role, "text": text, **extra}


def add_session(
    db_path,
    session_id,
    *,
    title="Custom session",
    messages=(),
    tool_calls=(),
    hidden=0,
    working_directory="/fixture/workspace/custom",
    created_ms=BASE_MS,
    last_ms=None,
):
    """Insert one session row plus optional nodes/tool calls into a fixture DB.

    ``messages`` are dicts serialized into ``chat_message``; ``tool_calls`` are
    ``(tool_call_json, tool_call_update_json)`` dict pairs.
    """
    last_ms = created_ms + 60_000 if last_ms is None else last_ms
    con = sqlite3.connect(db_path)
    with con:
        con.execute(
            "INSERT INTO sessions(id, working_directory, backend_type, model,"
            " agent_mode, created_at, last_activity_at, title, hidden)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                session_id,
                working_directory,
                "fixture-backend",
                "fixture-model",
                "fixture-mode",
                created_ms,
                last_ms,
                title,
                hidden,
            ),
        )
        for i, message in enumerate(messages, start=1):
            con.execute(
                "INSERT INTO message_nodes(session_id, node_id, parent_node_id,"
                " chat_message, created_at) VALUES (?, ?, ?, ?, ?)",
                (
                    session_id,
                    i,
                    None if i == 1 else i - 1,
                    json.dumps(message),
                    created_ms + i * 10_000,
                ),
            )
        for j, (call, update) in enumerate(tool_calls):
            con.execute(
                "INSERT INTO tool_call_state(session_id, tool_call_id,"
                " tool_call_json, tool_call_update_json) VALUES (?, ?, ?, ?)",
                (
                    session_id,
                    f"{session_id}-tc{j}",
                    json.dumps(call) if call is not None else None,
                    json.dumps(update) if update is not None else None,
                ),
            )
    con.close()
