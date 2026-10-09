"""PM-1: GUI sessions from ``state.vscdb`` merged into grouping."""

from __future__ import annotations

import json

import pytest
from conftest import create_state_vscdb, insert_vscdb_key
from devin_pm.cli import main
from devin_pm.projects import group_sessions, load_sessions
from devin_pm.vscdb import (
    GuiSession,
    default_state_vscdb,
    load_gui_sessions,
)


def test_load_gui_sessions(state_vscdb):
    sessions = {s.slug: s for s in load_gui_sessions(state_vscdb)}
    assert set(sessions) == {"canyon-newspaper", "river-fox"}
    fox = sessions["river-fox"]
    assert fox.backend == "acp/devin-cli"
    assert fox.workspace_id == "C:\\work\\gamma"
    assert fox.label == "gamma"
    assert fox.folders == ("C:\\work\\gamma",)
    assert fox.last_updated > 0


def test_gui_session_is_session_shaped(state_vscdb):
    fox = {s.slug: s for s in load_gui_sessions(state_vscdb)}["river-fox"]
    assert fox.id == "river-fox"
    assert fox.working_directory == "C:\\work\\gamma"
    assert fox.title == "gamma"
    assert fox.status == "gui"
    assert fox.source == "gui"
    assert fox.hidden is False
    assert fox.cogs_json is None
    assert fox.last_activity_at == fox.last_updated


def test_gui_working_directory_fallbacks():
    """Grouping key: workspaceId → folders[0] → label."""
    assert (
        GuiSession("s", "b", "ws", "lbl", ("f",), None).working_directory
        == "ws"
    )
    assert (
        GuiSession("s", "b", None, "lbl", ("f",), None).working_directory
        == "f"
    )
    assert (
        GuiSession("s", "b", None, "lbl", (), None).working_directory
        == "lbl"
    )
    assert GuiSession("s", "b", None, None, (), None).working_directory == ""


def test_malformed_binding_kept_with_null_attrs(tmp_path):
    """Best-effort: bad JSON still yields a session, grouped under '?'."""
    db = create_state_vscdb(tmp_path / "state.vscdb")
    insert_vscdb_key(
        db, "windsurfSpace.sessionWorkspace/acp/x/bad-slug", "not-json"
    )
    sessions = load_gui_sessions(db)
    assert len(sessions) == 1
    assert sessions[0].slug == "bad-slug"
    assert sessions[0].working_directory == ""


def test_key_without_backend_skipped(tmp_path):
    db = create_state_vscdb(tmp_path / "state.vscdb")
    insert_vscdb_key(
        db, "windsurfSpace.sessionWorkspace/lonely-slug", {"label": "x"}
    )
    assert load_gui_sessions(db) == []


def test_load_missing_file(tmp_path):
    from devin_internals.schema import SchemaDetectionError
    with pytest.raises(SchemaDetectionError):
        load_gui_sessions(tmp_path / "nope.vscdb")


def test_load_not_a_vscdb(tmp_path):
    junk = tmp_path / "state.vscdb"
    junk.write_bytes(b"junk")
    import sqlite3
    with pytest.raises(sqlite3.DatabaseError):
        load_gui_sessions(junk)


def test_default_state_vscdb_prefers_env(monkeypatch, tmp_path):
    db = tmp_path / "x.vscdb"
    monkeypatch.setenv("DEVIN_PM_STATE_VSCDB", str(db))
    assert default_state_vscdb() == db


def test_unified_grouping_merges_gui_into_cli(sessions_db, state_vscdb):
    """canyon-newspaper's workspaceId is alpha's dir → one project."""
    sessions = [
        *load_sessions(sessions_db),
        *load_gui_sessions(state_vscdb),
    ]
    projects = {p.name: p for p in group_sessions(sessions)}
    assert set(projects) == {"alpha", "beta", "gamma"}
    alpha = projects["alpha"]
    assert alpha.session_count == 4
    assert alpha.gui_session_count == 1
    assert "canyon-newspaper" in alpha.session_ids
    gamma = projects["gamma"]
    assert gamma.session_count == 1
    assert gamma.status_counts == {"gui": 1}


def test_status_table_marks_gui(sessions_db, state_vscdb, capsys):
    rc = main(
        [
            "status",
            "--sessions-db",
            str(sessions_db),
            "--vscdb",
            str(state_vscdb),
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "GUI" in out
    assert "gamma" in out


def test_status_table_unchanged_without_vscdb(sessions_db, capsys):
    assert main(["status", "--sessions-db", str(sessions_db)]) == 0
    assert "GUI" not in capsys.readouterr().out


def test_status_json_marks_gui(sessions_db, state_vscdb, capsys):
    rc = main(
        [
            "status",
            "--sessions-db",
            str(sessions_db),
            "--vscdb",
            str(state_vscdb),
            "--json",
        ]
    )
    assert rc == 0
    data = {p["name"]: p for p in json.loads(capsys.readouterr().out)}
    assert data["alpha"]["gui_sessions"] == 1
    assert data["alpha"]["sessions"] == 4
    assert data["gamma"]["status"] == {"gui": 1}
    assert data["beta"]["gui_sessions"] == 0


def test_report_marks_gui_source(sessions_db, state_vscdb, capsys):
    rc = main(
        [
            "report",
            "--sessions-db",
            str(sessions_db),
            "--vscdb",
            str(state_vscdb),
            "--project",
            "alpha",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "| gui |" in out
    assert "| cli |" in out
    assert "canyon-newspaper" in out


def test_vscdb_bare_flag_autodetect_warns_and_continues(
    sessions_db, monkeypatch, capsys, tmp_path
):
    """--vscdb with no PATH and no store found → warning + CLI-only."""
    monkeypatch.delenv("DEVIN_PM_STATE_VSCDB", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "empty"))
    monkeypatch.setenv("HOME", str(tmp_path / "nohome"))
    rc = main(
        ["status", "--sessions-db", str(sessions_db), "--vscdb"]
    )
    assert rc == 0
    err = capsys.readouterr().err
    assert "no state.vscdb" in err


def test_vscdb_missing_path_exits_2(sessions_db, tmp_path, capsys):
    missing = tmp_path / "no.vscdb"
    rc = main(
        [
            "status",
            "--sessions-db",
            str(sessions_db),
            "--vscdb",
            str(missing),
        ]
    )
    assert rc == 2
    assert "no state.vscdb" in capsys.readouterr().err


def test_registry_records_state_vscdb(sessions_db, state_vscdb, capsys):
    rc = main(
        [
            "registry",
            "--sessions-db",
            str(sessions_db),
            "--vscdb",
            str(state_vscdb),
        ]
    )
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["source"]["state_vscdb"].endswith("state.vscdb")
    alpha = {p["name"]: p for p in data["projects"]}["alpha"]
    assert alpha["gui_sessions"] == 1


def test_readonly_never_writes_vscdb(state_vscdb, sessions_db):
    """The CLI must open state.vscdb read-only — bytes stay untouched."""
    before = state_vscdb.read_bytes()
    main(
        [
            "status",
            "--sessions-db",
            str(sessions_db),
            "--vscdb",
            str(state_vscdb),
        ]
    )
    assert state_vscdb.read_bytes() == before
