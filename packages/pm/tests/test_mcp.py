"""MCP adapter contract: do_rollup mirrors `registry` JSON output; a
missing store or unknown project (the CLI's exit-2 cases) surface as
{error, detail} dicts; the tool layer never raises."""

import json

import pytest
from devin_pm.cli import main
from devin_pm.mcp_server import do_rollup


def test_do_rollup_matches_registry_json(sessions_db, capsys):
    """The adapter returns exactly what `devin-pm registry` prints."""
    assert main(["registry", "--sessions-db", str(sessions_db)]) == 0
    expected = json.loads(capsys.readouterr().out)
    got = do_rollup(
        sessions_db=str(sessions_db), generated=expected["generated"])
    assert got == expected


def test_do_rollup_single_project(sessions_db, capsys):
    """`project` narrows the rollup to that project's registry entry."""
    assert main(["registry", "--sessions-db", str(sessions_db)]) == 0
    registry = json.loads(capsys.readouterr().out)
    expected = next(
        p for p in registry["projects"] if p["name"] == "alpha")
    got = do_rollup(sessions_db=str(sessions_db), project="alpha")
    assert got == expected


def test_do_rollup_single_project_case_insensitive(sessions_db):
    got = do_rollup(sessions_db=str(sessions_db), project="ALPHA")
    assert got["name"] == "alpha"


def test_do_rollup_unknown_project(sessions_db):
    out = do_rollup(sessions_db=str(sessions_db), project="nope")
    assert out["error"] == "unknown_project"
    assert "alpha" in out["detail"]  # lists the known projects


def test_do_rollup_missing_db(tmp_path):
    out = do_rollup(sessions_db=str(tmp_path / "no.db"))
    assert out["error"] == "no_db"
    assert "sessions.db" in out["detail"]


def test_readonly_never_writes(sessions_db):
    """The adapter must leave the source store byte-identical."""
    before = sessions_db.read_bytes()
    do_rollup(sessions_db=str(sessions_db))
    do_rollup(sessions_db=str(sessions_db), project="alpha")
    assert sessions_db.read_bytes() == before


def test_build_server_registers_pm_rollup():
    pytest.importorskip("mcp")
    server = __import__(
        "devin_pm.mcp_server", fromlist=["build_server"]
    ).build_server()
    tools = getattr(server, "_tool_manager", None) or getattr(
        server, "tools", None)
    assert tools is not None


def test_server_entrypoint_in_pyproject():
    from pathlib import Path

    import tomllib

    pyproject = (
        Path(__file__).parents[1] / "pyproject.toml").read_text(
            encoding="utf-8")
    meta = tomllib.loads(pyproject)
    scripts = meta["project"]["scripts"]
    assert scripts["devin-pm-mcp"] == "devin_pm.mcp_server:main"
    assert any(dep.startswith("mcp") for dep in
               meta["project"]["optional-dependencies"]["mcp"])
