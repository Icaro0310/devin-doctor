import json
import sqlite3

import pytest
from devin_internals.fixtures import (
    create_acp_messages_db,
    create_sessions_db,
)

BASE_MS = 1_780_000_000_000


@pytest.fixture
def db_path(tmp_path):
    return create_sessions_db(tmp_path / "sessions.db")


@pytest.fixture
def acp_dir(tmp_path):
    d = tmp_path / "acp-messages"
    d.mkdir()
    return d


def msg(role, text, **extra):
    return {"role": role, "text": text, **extra}


def add_session(
    db_path,
    session_id,
    *,
    title="Custom session",
    messages=(),
    tool_calls=(),
    prompts=(),
    hidden=0,
    working_directory="/fixture/workspace/custom",
    created_ms=BASE_MS,
    last_ms=None,
):
    """Insert one session row plus optional nodes/tool calls/prompts.

    ``messages`` are dicts serialized into ``chat_message``; ``tool_calls``
    are ``(tool_call_json, tool_call_update_json)`` dict pairs; ``prompts``
    are ``(content, is_shell)`` tuples.
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
        for k, (content, is_shell) in enumerate(prompts):
            con.execute(
                "INSERT INTO prompt_history(content, timestamp, session_id,"
                " is_shell) VALUES (?, ?, ?, ?)",
                (content, created_ms + k * 5_000, session_id, is_shell),
            )
    con.close()


def add_acp_db(acp_dir, name, session_id, messages, *, created_ms=BASE_MS):
    """Create one ``acp-messages/<name>.db`` with ``(kind, payload)`` rows."""
    path = create_acp_messages_db(acp_dir / f"{name}.db")
    con = sqlite3.connect(path)
    with con:
        con.execute("DELETE FROM meta")
        con.execute("DELETE FROM messages")
        con.executemany(
            "INSERT INTO meta(key, value) VALUES (?, ?)",
            [
                ("fixture.session_id", session_id),
                ("fixture.created_at", str(created_ms)),
            ],
        )
        con.executemany(
            "INSERT INTO messages(position, kind, payload) VALUES (?, ?, ?)",
            [
                (pos, kind, json.dumps(payload))
                for pos, (kind, payload) in enumerate(messages)
            ],
        )
    con.close()
    return path
