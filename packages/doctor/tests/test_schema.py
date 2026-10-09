"""schema check: per-store version/shape detection via devin_internals."""

from devin_doctor.checks import schema
from devin_doctor.model import Context, Status
from devin_internals.fixtures import create_sessions_db


def test_healthy_all_recognized(ctx):
    findings = schema.run(ctx)
    assert all(f.status is Status.PASS for f in findings)
    sessions = next(f for f in findings if "sessions.db" in f.message)
    assert "v17" in sessions.message


def test_unknown_schema_version_fails(broken_ctx):
    """broken fixture writes schema_version=99 (> LATEST_KNOWN_SCHEMA)."""
    sessions = next(
        f for f in schema.run(broken_ctx) if "sessions.db" in f.message
    )
    assert sessions.status is Status.FAIL
    assert "unknown" in sessions.message.lower() or "99" in sessions.message
    assert sessions.fix


def test_known_but_unsupported_version_fails(ctx):
    create_sessions_db(ctx.data_dir / "cli" / "sessions.db", schema_version=14)
    sessions = next(
        f for f in schema.run(ctx) if "sessions.db" in f.message
    )
    assert sessions.status is Status.FAIL
    assert "14" in sessions.message


def test_older_supported_version_passes(ctx):
    create_sessions_db(ctx.data_dir / "cli" / "sessions.db", schema_version=16)
    sessions = next(
        f for f in schema.run(ctx) if "sessions.db" in f.message
    )
    assert sessions.status is Status.PASS
    assert "v16" in sessions.message


def test_missing_sessions_db_warns_skip(broken_ctx):
    """Broken fixture has sessions.db (unknown version); missing-file case
    needs an empty dir."""
    ctx = Context(data_dir=broken_ctx.data_dir.parent / "empty", cwd=broken_ctx.cwd)
    ctx.data_dir.mkdir(parents=True)
    sessions = next(
        f for f in schema.run(ctx) if "sessions.db" in f.message
    )
    assert sessions.status is Status.WARN
    assert "skipped" in sessions.message.lower() or "missing" in sessions.message.lower()


def test_missing_acp_dir_is_neutral(broken_ctx):
    acp = next(f for f in schema.run(broken_ctx) if "acp" in f.message)
    assert acp.status in (Status.PASS, Status.WARN)


def test_corrupt_sessions_db_fails(ctx):
    (ctx.data_dir / "cli" / "sessions.db").write_bytes(b"junk junk junk")
    sessions = next(
        f for f in schema.run(ctx) if "sessions.db" in f.message
    )
    assert sessions.status is Status.FAIL


def test_acp_db_wrong_shape_fails(ctx):
    import sqlite3

    bad = ctx.data_dir / "User" / "acp-messages" / "bogus.db"
    con = sqlite3.connect(bad)
    con.execute("CREATE TABLE something_else (x INTEGER)")
    con.close()
    acp = next(f for f in schema.run(ctx) if "acp" in f.message)
    assert acp.status is Status.FAIL
    assert "bogus.db" in acp.message
