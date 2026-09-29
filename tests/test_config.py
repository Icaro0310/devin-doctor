"""config check: credentials.toml presence (masked) and .devin/
hooks/mcp config sanity."""

from devin_doctor.checks import config
from devin_doctor.model import Context, Status


def _finding(findings, needle):
    return next(f for f in findings if needle in f.message)


def test_healthy_credentials_masked(ctx):
    f = _finding(config.run(ctx), "credentials.toml")
    assert f.status is Status.PASS
    assert "masked" in f.message
    # value from conftest must never leak into output
    for finding in config.run(ctx):
        assert "fixture-token" not in finding.message
        assert not finding.fix or "fixture-token" not in finding.fix


def test_missing_credentials_warns(broken_ctx):
    f = _finding(config.run(broken_ctx), "credentials.toml")
    assert f.status is Status.WARN
    assert f.fix


def test_invalid_credentials_fails(ctx):
    (ctx.data_dir / "credentials.toml").write_text("[broken\n", "utf-8")
    f = _finding(config.run(ctx), "credentials.toml")
    assert f.status is Status.FAIL


def test_no_devin_dir_passes(ctx):
    f = _finding(config.run(ctx), ".devin")
    assert f.status is Status.PASS


def test_valid_hooks_file_passes(ctx):
    devin_dir = ctx.cwd / ".devin"
    devin_dir.mkdir()
    (devin_dir / "hooks.v1.json").write_text(
        '// hooks are fine\n{"PreToolUse": [{"matcher": "exec",'
        ' "hooks": [{"type": "command", "command": "./check.sh"}]}]}',
        "utf-8",
    )
    f = _finding(config.run(ctx), "hooks.v1.json")
    assert f.status is Status.PASS


def test_invalid_json_in_hooks_file_fails(ctx):
    devin_dir = ctx.cwd / ".devin"
    devin_dir.mkdir()
    (devin_dir / "hooks.v1.json").write_text("{not json", "utf-8")
    f = _finding(config.run(ctx), "hooks.v1.json")
    assert f.status is Status.FAIL


def test_unknown_hook_event_warns(ctx):
    devin_dir = ctx.cwd / ".devin"
    devin_dir.mkdir()
    (devin_dir / "hooks.v1.json").write_text(
        '{"NoSuchEvent": [{"hooks": []}]}', "utf-8"
    )
    f = _finding(config.run(ctx), "hooks.v1.json")
    assert f.status is Status.WARN
    assert "NoSuchEvent" in f.message


def test_malformed_hooks_structure_fails(ctx):
    devin_dir = ctx.cwd / ".devin"
    devin_dir.mkdir()
    (devin_dir / "hooks.v1.json").write_text(
        '{"PreToolUse": "nope"}', "utf-8"
    )
    f = _finding(config.run(ctx), "hooks.v1.json")
    assert f.status is Status.FAIL


def test_mcp_config_ok(ctx):
    devin_dir = ctx.cwd / ".devin"
    devin_dir.mkdir()
    (devin_dir / "mcp_config.json").write_text(
        '{"mcpServers": {"x": {"command": "srv"}}}', "utf-8"
    )
    f = _finding(config.run(ctx), ".devin/mcp_config.json")
    assert f.status is Status.PASS


def test_mcp_config_missing_servers_key_warns(ctx):
    devin_dir = ctx.cwd / ".devin"
    devin_dir.mkdir()
    (devin_dir / "mcp_config.json").write_text('{"oops": {}}', "utf-8")
    f = _finding(config.run(ctx), ".devin/mcp_config.json")
    assert f.status is Status.WARN


def test_legacy_mcpservers_in_config_warns(ctx):
    devin_dir = ctx.cwd / ".devin"
    devin_dir.mkdir()
    (devin_dir / "config.json").write_text(
        '{"mcpServers": {"x": {"command": "srv"}}}', "utf-8"
    )
    f = _finding(config.run(ctx), ".devin/config.json")
    assert f.status is Status.WARN
    assert "mcp_config" in f.message or "mcpServers" in f.message


def test_user_config_in_data_dir_invalid_fails(ctx):
    (ctx.data_dir / "config.json").write_text("{bad json", "utf-8")
    f = _finding(config.run(ctx), "config.json")
    assert f.status is Status.FAIL


def test_child_repo_devin_dir_checked(tmp_path, data_dir):
    repo = tmp_path / "child-repo"
    (repo / ".devin").mkdir(parents=True)
    (repo / ".devin" / "hooks.v1.json").write_text("{broken", "utf-8")
    ctx = Context(data_dir=data_dir, cwd=tmp_path)
    f = _finding(config.run(ctx), "child-repo")
    assert f.status is Status.FAIL
