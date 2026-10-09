"""stores check: locate the three stores, report present/missing, sizes,
row counts."""

from devin_doctor.checks import stores
from devin_doctor.model import Status


def test_healthy_data_dir_all_present(ctx):
    findings = stores.run(ctx)
    statuses = {f.status for f in findings}
    assert Status.FAIL not in statuses
    assert Status.WARN not in statuses
    sessions = next(f for f in findings if "sessions.db" in f.message)
    assert sessions.status is Status.PASS
    assert "3 sessions" in sessions.message
    acp = next(f for f in findings if "acp-messages" in f.message)
    assert acp.status is Status.PASS
    assert "2" in acp.message
    vscdb = next(f for f in findings if "state.vscdb" in f.message)
    assert vscdb.status is Status.PASS


def test_broken_data_dir_reports_missing(broken_ctx):
    findings = stores.run(broken_ctx)
    assert any(f.status is Status.FAIL for f in findings)
    assert any(f.status is Status.WARN for f in findings)


def test_missing_sessions_db_is_fail(broken_ctx):
    findings = stores.run(broken_ctx)
    sessions = next(f for f in findings if "sessions.db" in f.message)
    assert sessions.status is Status.FAIL
    assert sessions.fix


def test_missing_acp_dir_is_warn(broken_ctx):
    findings = stores.run(broken_ctx)
    acp = next(f for f in findings if "acp-messages" in f.message)
    assert acp.status is Status.WARN


def test_missing_state_vscdb_is_warn(broken_ctx):
    findings = stores.run(broken_ctx)
    vscdb = next(f for f in findings if "state.vscdb" in f.message)
    assert vscdb.status is Status.WARN


def test_missing_data_dir_fails_cleanly(tmp_path):
    from devin_doctor.model import Context

    ctx = Context(data_dir=tmp_path / "nope", cwd=tmp_path)
    findings = stores.run(ctx)
    assert any(f.status is Status.FAIL for f in findings)
    first = findings[0]
    assert "not found" in first.message or "missing" in first.message.lower()
    assert first.fix


def test_corrupt_sessions_db_is_fail(ctx):
    bad = ctx.data_dir / "cli" / "sessions.db"
    bad.write_bytes(b"not a sqlite database at all")
    findings = stores.run(ctx)
    sessions = next(f for f in findings if "sessions.db" in f.message)
    assert sessions.status is Status.FAIL
