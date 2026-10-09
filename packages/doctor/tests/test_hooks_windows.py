"""hooks-windows check: hooks/MCP commands that would pop a console window
on Windows, each reported with file, hook event and a wrapper fix."""

import json

from devin_doctor.checks import hooks_windows
from devin_doctor.model import Context, Status


def _finding(findings, needle):
    return next(f for f in findings if needle in f.message)


def _hooks_file(path, command, event="PreToolUse"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {event: [{"hooks": [{"type": "command", "command": command}]}]}
        ),
        "utf-8",
    )


# ---------------------------------------------------------------------------
# pattern unit tests
# ---------------------------------------------------------------------------


def test_cmd_c_without_wrapper_flagged():
    issues = hooks_windows.console_window_issues("cmd /c echo hi")
    assert issues and "cmd" in issues[0][0]


def test_cmd_c_with_start_min_ok():
    assert not hooks_windows.console_window_issues(
        'cmd /c start /min "" mytool.exe'
    )


def test_powershell_without_windowstyle_flagged():
    issues = hooks_windows.console_window_issues(
        "powershell.exe -NoProfile -File C:\\x\\hook.ps1"
    )
    assert any("WindowStyle" in problem for problem, _ in issues)


def test_powershell_hidden_ok():
    assert not hooks_windows.console_window_issues(
        "powershell -NoProfile -WindowStyle Hidden -File C:\\x\\hook.ps1"
    )


def test_python_exe_flagged_pythonw_ok():
    issues = hooks_windows.console_window_issues(
        "C:\\Python311\\python.exe C:\\x\\hook.py"
    )
    assert any("pythonw" in fix for _, fix in issues)
    assert not hooks_windows.console_window_issues(
        "C:\\Python311\\pythonw.exe C:\\x\\hook.py"
    )


def test_python3_exe_flagged():
    assert hooks_windows.console_window_issues("python3.exe hook.py")


def test_direct_bat_flagged():
    issues = hooks_windows.console_window_issues("C:\\tools\\deploy.bat")
    assert issues and ".bat" in issues[0][0]


def test_direct_ps1_flagged_but_powershell_file_not_double_flagged():
    issues = hooks_windows.console_window_issues("C:\\tools\\deploy.ps1")
    assert any(".ps1" in problem for problem, _ in issues)
    # powershell launching a ps1 without hidden style → powershell rule only
    issues = hooks_windows.console_window_issues(
        "powershell -File C:\\tools\\deploy.ps1"
    )
    assert len(issues) == 1
    assert "powershell" in issues[0][0]


def test_posix_python3_not_flagged():
    assert not hooks_windows.console_window_issues("python3 /opt/hook.py")


# ---------------------------------------------------------------------------
# check-level tests
# ---------------------------------------------------------------------------


def test_no_entries_passes(ctx):
    findings = hooks_windows.run(ctx)
    assert len(findings) == 1
    assert findings[0].status is Status.PASS


def test_project_hooks_flagged(ctx):
    _hooks_file(
        ctx.cwd / ".devin" / "hooks.v1.json",
        "powershell.exe -File C:\\x\\hook.ps1",
        event="SessionStart",
    )
    f = _finding(hooks_windows.run(ctx), "SessionStart")
    assert f.status is Status.WARN
    assert "hooks.v1.json" in f.message
    assert f.fix and "WindowStyle Hidden" in f.fix


def test_user_config_hooks_flagged(ctx):
    (ctx.data_dir / "config.json").write_text(
        json.dumps(
            {
                "hooks": {
                    "Stop": [
                        {
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": "cmd /c cleanup.bat",
                                }
                            ]
                        }
                    ]
                }
            }
        ),
        "utf-8",
    )
    findings = [f for f in hooks_windows.run(ctx) if f.status is Status.WARN]
    assert findings
    # 'cmd /c' and direct '.bat' are both reported for this entry
    assert "cmd" in findings[0].message
    assert ".bat" in findings[0].message
    assert findings[0].fix


def test_user_mcp_server_python_exe_flagged(ctx):
    (ctx.data_dir / "mcp_config.json").write_text(
        json.dumps(
            {
                "mcpServers": {
                    "noisy": {
                        "command": "python.exe",
                        "args": ["C:\\srv\\server.py"],
                    }
                }
            }
        ),
        "utf-8",
    )
    f = _finding(hooks_windows.run(ctx), "mcpServers.noisy")
    assert f.status is Status.WARN
    assert f.fix and "pythonw" in f.fix


def test_settings_json_hooks_scanned(ctx):
    user_dir = ctx.data_dir / "User"
    (user_dir / "settings.json").write_text(
        json.dumps(
            {
                "hooks": {
                    "UserPromptSubmit": [
                        {"hooks": [{"type": "command",
                                    "command": "cmd /c noisy.bat"}]}
                    ]
                }
            }
        ),
        "utf-8",
    )
    f = _finding(hooks_windows.run(ctx), "User/settings.json")
    assert f.status is Status.WARN


def test_child_repo_devin_dir_checked(tmp_path, data_dir):
    repo = tmp_path / "child-repo"
    _hooks_file(
        repo / ".devin" / "hooks.v1.json",
        "C:\\tools\\run.bat",
    )
    ctx = Context(data_dir=data_dir, cwd=tmp_path)
    f = _finding(hooks_windows.run(ctx), "child-repo/.devin/hooks.v1.json")
    assert f.status is Status.WARN


def test_invalid_json_skipped(ctx):
    devin_dir = ctx.cwd / ".devin"
    devin_dir.mkdir()
    (devin_dir / "hooks.v1.json").write_text("{broken", "utf-8")
    findings = hooks_windows.run(ctx)
    assert len(findings) == 1
    assert findings[0].status is Status.PASS


def test_url_only_mcp_server_not_scanned(ctx):
    (ctx.data_dir / "mcp_config.json").write_text(
        json.dumps({"mcpServers": {"web": {"url": "http://x/mcp"}}}),
        "utf-8",
    )
    findings = hooks_windows.run(ctx)
    assert len(findings) == 1
    assert findings[0].status is Status.PASS
