"""PM-3: path normalization for grouping keys."""

from __future__ import annotations

from conftest import insert_session

from devin_pm.paths import normalize_path
from devin_pm.projects import group_sessions, load_sessions
from devin_pm.vscdb import GuiSession


def test_windows_spellings_fold():
    """C:\\x, C:/x and /c/x are one grouping key (case-insensitive FS)."""
    expected = "c:/users/x/repo"
    assert normalize_path("C:\\Users\\X\\repo") == expected
    assert normalize_path("C:/Users/X/repo") == expected
    assert normalize_path("/c/Users/X/repo") == expected
    assert normalize_path("/cygdrive/c/Users/X/repo") == expected


def test_trailing_and_duplicate_separators():
    assert normalize_path("C:\\work\\alpha\\") == "c:/work/alpha"
    assert normalize_path("/home/u//repo/") == "/home/u/repo"


def test_wsl_unc_maps_to_posix():
    """\\\\wsl.localhost\\<distro>\\home\\u\\repo ≡ /home/u/repo."""
    unc = "\\\\wsl.localhost\\Ubuntu\\home\\u\\repo"
    assert normalize_path(unc) == "/home/u/repo"
    assert normalize_path("\\\\wsl$\\Debian\\home\\u\\repo") == "/home/u/repo"


def test_posix_case_preserved():
    """POSIX is case-sensitive — Foo and foo stay distinct projects."""
    assert normalize_path("/home/u/Foo") == "/home/u/Foo"
    assert normalize_path("/home/u/Foo") != normalize_path("/home/u/foo")


def test_edge_cases():
    assert normalize_path("") == ""
    assert normalize_path("alpha") == "alpha"
    assert normalize_path("/") == "/"
    assert normalize_path("C:\\") == "c:"
    assert normalize_path("/c") == "c:"


def test_grouping_folds_windows_and_msys(sessions_db):
    """Sessions under C:\\ and /c/ spellings land in one project."""
    insert_session(
        sessions_db, sid="g-1", working_directory="C:\\work\\gamma"
    )
    insert_session(
        sessions_db, sid="g-2", working_directory="/c/work/gamma"
    )
    projects = {p.name: p for p in group_sessions(load_sessions(sessions_db))}
    assert sorted(projects["gamma"].session_ids) == ["g-1", "g-2"]


def test_grouping_keeps_original_path_for_display(sessions_db):
    """The grouping key is normalized; members keep original spellings."""
    insert_session(
        sessions_db, sid="g-1", working_directory="C:\\work\\gamma"
    )
    insert_session(
        sessions_db, sid="g-2", working_directory="/c/work/gamma"
    )
    projects = {p.name: p for p in group_sessions(load_sessions(sessions_db))}
    originals = {s.working_directory for s in projects["gamma"].sessions}
    assert originals == {"C:\\work\\gamma", "/c/work/gamma"}


def test_gui_session_groups_with_cli_session(sessions_db):
    """A GUI workspace written MSYS-style merges with the CLI project."""
    insert_session(
        sessions_db, sid="g-1", working_directory="C:\\work\\gamma"
    )
    gui = GuiSession(
        slug="river-fox",
        backend="acp/devin-cli",
        workspace_id="/c/work/gamma",
        label="gamma",
        folders=(),
        last_updated=2_000,
    )
    projects = {
        p.name: p
        for p in group_sessions([*load_sessions(sessions_db), gui])
    }
    gamma = projects["gamma"]
    assert sorted(gamma.session_ids) == ["g-1", "river-fox"]
    assert gamma.gui_session_count == 1
