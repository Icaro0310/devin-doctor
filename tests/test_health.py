"""health-of-data check: empty sessions, orphan message_nodes, stale
sessions, locked databases."""

import sqlite3

from devin_internals.fixtures import _BASE_TS_MS

from devin_doctor.checks import health
from devin_doctor.model import Context, Status

from conftest import lock_db_exclusively


def _finding(findings, needle):
    return next(f for f in findings if needle in f.message)


def test_healthy_all_pass(ctx):
    findings = health.run(ctx)
    assert all(f.status is Status.PASS for f in findings), [
        (f.status, f.message) for f in findings
    ]


def test_empty_sessions_warn(ctx):
    con = sqlite3.connect(ctx.data_dir / "cli" / "sessions.db")
    with con:
        con.execute(
            "INSERT INTO sessions(id, working_directory, backend_type, model,"
            " agent_mode, created_at, last_activity_at)"
            " VALUES ('empty-fixture-session', '/x', 'b', 'm', 'mode', ?, ?)",
            (_BASE_TS_MS, _BASE_TS_MS),
        )
    con.close()
    findings = health.run(ctx)
    f = _finding(findings, "empty")
    assert f.status is Status.WARN
    assert "1" in f.message


def test_orphan_message_nodes_warn(ctx):
    con = sqlite3.connect(ctx.data_dir / "cli" / "sessions.db")
    with con:
        con.execute(
            "INSERT INTO message_nodes(session_id, node_id, chat_message,"
            " created_at) VALUES ('ghost-session', 1, '{}', ?)",
            (_BASE_TS_MS,),
        )
    con.close()
    findings = health.run(ctx)
    f = _finding(findings, "orphan")
    assert f.status is Status.WARN
    assert "1" in f.message


def test_stale_sessions_warn(ctx):
    ctx.now_ms = _BASE_TS_MS + 400 * 86_400_000  # ~400 days later
    findings = health.run(ctx)
    f = _finding(findings, "inactive")
    assert f.status is Status.WARN
    assert "3" in f.message


def test_no_stale_when_recent(ctx):
    findings = health.run(ctx)
    f = _finding(findings, "inactive")
    assert f.status is Status.PASS


def test_locked_db_warns(ctx):
    db = ctx.data_dir / "cli" / "sessions.db"
    holder = lock_db_exclusively(db)
    try:
        findings = health.run(ctx)
        f = _finding(findings, "SQLITE_BUSY")
        assert f.status is Status.WARN
        assert "running" in f.message.lower() or "busy" in f.message.lower()
    finally:
        holder.rollback()
        holder.close()


def test_zero_sessions_warns(tmp_path):
    from devin_internals.fixtures import create_sessions_db

    root = tmp_path / "devin"
    create_sessions_db(root / "cli" / "sessions.db", n_sessions=0)
    ctx = Context(data_dir=root, cwd=tmp_path, now_ms=_BASE_TS_MS + 10**9)
    f = _finding(health.run(ctx), "0 sessions")
    assert f.status is Status.WARN


def test_unreadable_sessions_db_skips(ctx):
    (ctx.data_dir / "cli" / "sessions.db").write_bytes(b"junk")
    findings = health.run(ctx)
    f = _finding(findings, "sessions.db")
    assert f.status is Status.WARN
    assert "skipped" in f.message.lower() or "unreadable" in f.message.lower()
