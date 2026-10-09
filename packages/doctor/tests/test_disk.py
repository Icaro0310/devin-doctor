"""disk check: total data-dir size, largest DBs, acp-messages accumulation."""

from devin_doctor.checks import disk
from devin_doctor.model import Status


def _finding(findings, needle):
    return next(f for f in findings if needle in f.message)


def test_healthy_all_pass(ctx):
    findings = disk.run(ctx)
    assert all(f.status is Status.PASS for f in findings), [
        f.message for f in findings
    ]


def test_reports_total_size(ctx):
    f = _finding(disk.run(ctx), "total")
    assert f.status is Status.PASS
    assert "files" in f.message


def test_reports_largest_stores(ctx):
    f = _finding(disk.run(ctx), "largest")
    assert f.status is Status.PASS
    assert "sessions.db" in f.message


def test_acp_accumulation_reported(ctx):
    f = _finding(disk.run(ctx), "acp-messages")
    assert "2" in f.message


def test_oversized_total_warns(ctx):
    ctx.total_warn_bytes = 1  # any non-empty dir trips it
    f = _finding(disk.run(ctx), "total")
    assert f.status is Status.WARN
    assert f.fix


def test_oversized_store_warns(ctx):
    ctx.store_warn_bytes = 1
    f = _finding(disk.run(ctx), "largest")
    assert f.status is Status.WARN


def test_acp_accumulation_warns(ctx):
    ctx.acp_warn_bytes = 1
    f = _finding(disk.run(ctx), "acp-messages")
    assert f.status is Status.WARN


def test_missing_data_dir_fails(tmp_path):
    from devin_doctor.model import Context

    ctx = Context(data_dir=tmp_path / "nope", cwd=tmp_path)
    findings = disk.run(ctx)
    assert findings[0].status is Status.FAIL
