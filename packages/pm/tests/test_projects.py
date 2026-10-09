"""Grouping sessions into projects (tests first)."""

from __future__ import annotations

from devin_pm.projects import (
    default_sessions_db,
    extract_cost,
    group_sessions,
    load_sessions,
    project_name,
)


def test_project_name_strips_separators_and_trailing_slash():
    assert project_name("C:\\work\\alpha") == "alpha"
    assert project_name("C:\\work\\alpha\\") == "alpha"
    assert project_name("/home/dev/beta") == "beta"
    assert project_name("/home/dev/beta/") == "beta"
    assert project_name("\\\\wsl.localhost\\Ubuntu\\home\\dev\\proj") == "proj"
    assert project_name("alpha") == "alpha"


def test_project_name_edge_cases():
    assert project_name("") == "?"
    assert project_name("/") == "?"
    assert project_name("C:\\") == "C:"


def test_group_sessions_by_working_directory(sessions_db):
    projects = group_sessions(load_sessions(sessions_db))
    assert {p.name for p in projects} == {"alpha", "beta"}


def test_group_normalizes_trailing_separator(sessions_db):
    """a-2's working_directory has a trailing sep — still lands in alpha."""
    projects = {p.name: p for p in group_sessions(load_sessions(sessions_db))}
    assert projects["alpha"].session_count == 3
    assert sorted(projects["alpha"].session_ids) == ["a-1", "a-2", "a-3"]


def test_project_rollup_fields(sessions_db):
    projects = {p.name: p for p in group_sessions(load_sessions(sessions_db))}
    alpha = projects["alpha"]
    assert alpha.working_directory.rstrip("/\\").endswith("alpha")
    assert alpha.last_activity_at == max(
        s.last_activity_at for s in alpha.sessions
    )
    assert alpha.status_counts == {"active": 2, "hidden": 1}
    beta = projects["beta"]
    assert beta.session_count == 2
    assert beta.status_counts == {"active": 2}


def test_projects_sorted_by_last_activity_desc(sessions_db):
    projects = group_sessions(load_sessions(sessions_db))
    last = [p.last_activity_at for p in projects]
    assert last == sorted(last, reverse=True)


def test_extract_cost_best_effort():
    assert extract_cost('{"cost": 0.25}') == 0.25
    assert extract_cost('{"totals": {"cost_usd": 0.5}}') == 0.5
    assert extract_cost('{"synthetic": true}') is None
    assert extract_cost(None) is None
    assert extract_cost("not json") is None


def test_project_cost_sums_known_values(sessions_db):
    projects = {p.name: p for p in group_sessions(load_sessions(sessions_db))}
    assert projects["alpha"].cost == 0.75
    assert projects["beta"].cost is None


def test_load_sessions_returns_all(sessions_db):
    sessions = load_sessions(sessions_db)
    assert len(sessions) == 5
    assert {s.id for s in sessions} == {"a-1", "a-2", "a-3", "b-1", "b-2"}


def test_load_sessions_missing_file(tmp_path):
    import pytest
    from devin_internals.schema import SchemaDetectionError
    with pytest.raises(SchemaDetectionError):
        load_sessions(tmp_path / "nope.db")


def test_default_sessions_db_prefers_env(monkeypatch, tmp_path):
    db = tmp_path / "x.db"
    monkeypatch.setenv("DEVIN_PM_SESSIONS_DB", str(db))
    assert default_sessions_db() == db


def test_default_sessions_db_windows_appdata(monkeypatch, tmp_path):
    monkeypatch.delenv("DEVIN_PM_SESSIONS_DB", raising=False)
    monkeypatch.setenv("APPDATA", str(tmp_path))
    import sys

    monkeypatch.setattr(sys, "platform", "win32")
    expected = tmp_path / "devin" / "cli" / "sessions.db"
    assert default_sessions_db() == expected


def test_default_sessions_db_linux_falls_back_to_config_home(
    monkeypatch, tmp_path
):
    import sys

    monkeypatch.delenv("DEVIN_PM_SESSIONS_DB", raising=False)
    monkeypatch.setattr(sys, "platform", "linux")
    data_home = tmp_path / "data"
    config_home = tmp_path / "config"
    monkeypatch.setenv("XDG_DATA_HOME", str(data_home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_home))
    monkeypatch.setenv("HOME", str(tmp_path / "homeless"))
    db = config_home / "devin" / "cli" / "sessions.db"
    db.parent.mkdir(parents=True)
    db.touch()
    assert default_sessions_db() == db


def test_default_sessions_db_linux_prefers_data_home(monkeypatch, tmp_path):
    import sys

    monkeypatch.delenv("DEVIN_PM_SESSIONS_DB", raising=False)
    monkeypatch.setattr(sys, "platform", "linux")
    data_home = tmp_path / "data"
    config_home = tmp_path / "config"
    monkeypatch.setenv("XDG_DATA_HOME", str(data_home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_home))
    monkeypatch.setenv("HOME", str(tmp_path / "homeless"))
    for root in (data_home, config_home):
        db = root / "devin" / "cli" / "sessions.db"
        db.parent.mkdir(parents=True)
        db.touch()
    assert default_sessions_db() == data_home / "devin" / "cli" / "sessions.db"


def test_default_sessions_db_linux_returns_primary_when_missing(
    monkeypatch, tmp_path
):
    import sys

    monkeypatch.delenv("DEVIN_PM_SESSIONS_DB", raising=False)
    monkeypatch.setattr(sys, "platform", "linux")
    data_home = tmp_path / "data"
    monkeypatch.setenv("XDG_DATA_HOME", str(data_home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("HOME", str(tmp_path / "homeless"))
    assert (
        default_sessions_db() == data_home / "devin" / "cli" / "sessions.db"
    )


def test_group_empty():
    assert group_sessions([]) == []
