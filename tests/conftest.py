import json
import sqlite3

import pytest
from devin_internals.fixtures import create_sessions_db
from devin_internals.parsers import SessionsStore

BASE_MS = 1_780_000_000_000


@pytest.fixture
def db_path(tmp_path):
    return create_sessions_db(tmp_path / "sessions.db")


@pytest.fixture
def store(db_path):
    with SessionsStore(db_path) as s:
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
