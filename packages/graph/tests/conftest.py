import json
import sqlite3

import pytest
from devin_internals.fixtures import create_sessions_db

BASE_MS = 1_780_000_000_000

ALPHA = "/repo/alpha"
BETA = "/repo/beta"

# Synthetic acp::ToolCall payloads — the inner format is marked "unstable" in
# SCHEMA.md, so the fixture exercises several plausible shapes on purpose.
CALL_READ_APP = {
    "kind": "read",
    "title": "Read file",
    "rawInput": {"file_path": f"{ALPHA}/src/app.py"},
    "locations": [{"path": f"{ALPHA}/src/app.py"}],
}
CALL_RUN_PYTEST = {
    "kind": "execute",
    "title": "Run command",
    "rawInput": {"command": "python -m pytest tests/test_app.py -x"},
}
CALL_EDIT_MAIN = {
    "kind": "edit",
    "title": "Edit file",
    "rawInput": {"path": f"{BETA}/main.py"},
}
CALL_READ_APP_AGAIN = {
    "kind": "read",
    "title": "Read file",
    "rawInput": {"file_path": f"{ALPHA}/src/app.py"},
}
CALL_WRITE_DOCS = {
    "tool": "fs_write",
    "args": {"files": ["docs/README.md", "docs/notes.txt"]},
}


@pytest.fixture
def db_path(tmp_path):
    return create_sessions_db(tmp_path / "sessions.db")


@pytest.fixture
def sessions_db(tmp_path):
    """Controlled fixture: 3 sessions, 2 projects, shared file across projects."""
    p = create_sessions_db(tmp_path / "sessions.db", n_sessions=0)
    add_session(
        p, "sess-a", title="Alpha work", working_directory=ALPHA,
        created_ms=BASE_MS,
        tool_calls=[(CALL_READ_APP, None), (CALL_RUN_PYTEST, None), (None, None)],
    )
    add_session(
        p, "sess-b", title="Beta work", working_directory=BETA,
        created_ms=BASE_MS + 3_600_000,
        tool_calls=[(CALL_EDIT_MAIN, None), (CALL_READ_APP_AGAIN, None)],
    )
    add_session(
        p, "sess-c", title="Alpha docs", working_directory=ALPHA,
        created_ms=BASE_MS + 7_200_000,
        tool_calls=[(CALL_WRITE_DOCS, None)],
    )
    return p


def add_session(
    db_path,
    session_id,
    *,
    title="Custom session",
    tool_calls=(),
    working_directory="/fixture/workspace/custom",
    created_ms=BASE_MS,
    last_ms=None,
    hidden=0,
):
    """Insert one session row plus tool_call_state rows into a fixture DB.

    ``tool_calls`` are ``(tool_call_json, tool_call_update_json)`` dict pairs;
    either side may be ``None`` (interrupted call).
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


def add_tool_call(db_path, session_id, tool_call_id, call, update=None):
    con = sqlite3.connect(db_path)
    with con:
        con.execute(
            "INSERT INTO tool_call_state(session_id, tool_call_id,"
            " tool_call_json, tool_call_update_json) VALUES (?, ?, ?, ?)",
            (
                session_id,
                tool_call_id,
                json.dumps(call) if call is not None else None,
                json.dumps(update) if update is not None else None,
            ),
        )
    con.close()


def bump_last_activity(db_path, session_id, last_ms):
    con = sqlite3.connect(db_path)
    with con:
        con.execute(
            "UPDATE sessions SET last_activity_at = ? WHERE id = ?",
            (last_ms, session_id),
        )
    con.close()


def delete_session(db_path, session_id):
    con = sqlite3.connect(db_path)
    with con:
        con.execute(
            "DELETE FROM tool_call_state WHERE session_id = ?", (session_id,))
        con.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
    con.close()


def delete_tool_call(db_path, session_id, tool_call_id):
    con = sqlite3.connect(db_path)
    with con:
        con.execute(
            "DELETE FROM tool_call_state WHERE session_id = ? AND tool_call_id = ?",
            (session_id, tool_call_id),
        )
    con.close()
