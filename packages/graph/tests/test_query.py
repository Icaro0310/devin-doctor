"""Canned queries over a built graph.db."""

import pytest
from devin_internals.parsers import SessionsStore

from devin_graph.query import (
    project_detail,
    projects_graph,
    sessions_for_file,
    sessions_for_tool,
    shared_files,
    tools_for_project,
)
from devin_graph.store import GraphStore

from conftest import ALPHA, BETA


@pytest.fixture
def graph(sessions_db, tmp_path):
    with SessionsStore(sessions_db) as ss:
        gs = GraphStore(tmp_path / "graph.db")
        gs.build(ss)
        yield gs
        gs.close()


# -- sessions_for_file ---------------------------------------------------------


def test_sessions_for_file_exact(graph):
    res = sessions_for_file(graph, f"{ALPHA}/tests/test_app.py")
    assert res["files"] == [f"{ALPHA}/tests/test_app.py"]
    assert [s["id"] for s in res["sessions"]] == ["sess-a"]
    assert [t["id"] for t in res["tool_calls"]] == ["sess-a:sess-a-tc1"]


def test_sessions_for_file_suffix_match(graph):
    """A relative/basename query still finds the absolute stored path."""
    res = sessions_for_file(graph, "src/app.py")
    assert res["files"] == [f"{ALPHA}/src/app.py"]
    assert [s["id"] for s in res["sessions"]] == ["sess-a", "sess-b"]


def test_sessions_for_file_no_match(graph):
    res = sessions_for_file(graph, "nope/missing.py")
    assert res["files"] == []
    assert res["sessions"] == []
    assert res["tool_calls"] == []


# -- sessions_for_tool ---------------------------------------------------------


def test_sessions_for_tool(graph):
    res = sessions_for_tool(graph, "read")
    assert [s["id"] for s in res["sessions"]] == ["sess-a", "sess-b"]
    assert res["projects"] == sorted([ALPHA, BETA])


def test_sessions_for_tool_case_insensitive_and_unknown(graph):
    assert [s["id"] for s in sessions_for_tool(graph, "READ")["sessions"]] \
        == ["sess-a", "sess-b"]
    res = sessions_for_tool(graph, "nonexistent")
    assert res["sessions"] == [] and res["projects"] == []


# -- tools_for_project / project_detail ----------------------------------------


def test_tools_for_project_by_name(graph):
    res = tools_for_project(graph, "alpha")
    assert res["projects"] == [ALPHA]
    assert res["tools"] == ["execute", "fs_write", "read"]
    assert [s["id"] for s in res["sessions"]] == ["sess-a", "sess-c"]


def test_tools_for_project_by_path(graph):
    res = tools_for_project(graph, BETA)
    assert res["tools"] == ["edit", "read"]
    assert [s["id"] for s in res["sessions"]] == ["sess-b"]


def test_tools_for_project_no_match(graph):
    res = tools_for_project(graph, "nothing")
    assert res["projects"] == [] and res["tools"] == []


def test_project_detail(graph):
    res = project_detail(graph, "alpha")
    assert res["project"] == ALPHA
    assert [s["id"] for s in res["sessions"]] == ["sess-a", "sess-c"]
    assert res["tools"] == ["execute", "fs_write", "read"]
    assert res["files"] == [
        f"{ALPHA}/docs/README.md",
        f"{ALPHA}/docs/notes.txt",
        f"{ALPHA}/src/app.py",
        f"{ALPHA}/tests/test_app.py",
    ]


# -- projects_graph ------------------------------------------------------------


def test_projects_graph_adjacency(graph):
    data = projects_graph(graph)
    assert {n["id"] for n in data["nodes"]} == {ALPHA, BETA}
    assert len(data["links"]) == 1
    link = data["links"][0]
    assert {link["source"], link["target"]} == {ALPHA, BETA}
    # shared tool 'read' + shared file src/app.py → weight 2
    assert link["shared_tools"] == ["read"]
    assert link["shared_files"] == [f"{ALPHA}/src/app.py"]
    assert link["weight"] == 2


def test_projects_graph_empty(tmp_path, sessions_db):
    import sqlite3
    con = sqlite3.connect(sessions_db)
    with con:
        con.execute("DELETE FROM tool_call_state")
        con.execute("DELETE FROM sessions")
    con.close()
    with SessionsStore(sessions_db) as ss, GraphStore(
            tmp_path / "empty.db") as gs:
        gs.build(ss)
        assert projects_graph(gs) == {"nodes": [], "links": []}


# -- shared_files --------------------------------------------------------------


def test_shared_files_cross_project(graph):
    """src/app.py is read by sess-a (alpha) and sess-b (beta)."""
    res = shared_files(graph)
    assert res["count"] == 1
    (entry,) = res["files"]
    assert entry["file"] == f"{ALPHA}/src/app.py"
    assert entry["name"] == "app.py"
    assert entry["projects"] == sorted([ALPHA, BETA])
    assert entry["sessions"] == ["sess-a", "sess-b"]


def test_shared_files_excludes_single_project_files(graph):
    """main.py and the docs files are touched by one project only."""
    res = shared_files(graph)
    files = {f["file"] for f in res["files"]}
    assert f"{BETA}/main.py" not in files
    assert f"{ALPHA}/docs/README.md" not in files
    assert f"{ALPHA}/tests/test_app.py" not in files


def test_shared_files_empty(tmp_path, sessions_db):
    import sqlite3
    con = sqlite3.connect(sessions_db)
    with con:
        con.execute("DELETE FROM tool_call_state")
        con.execute("DELETE FROM sessions")
    con.close()
    with SessionsStore(sessions_db) as ss, GraphStore(
            tmp_path / "empty.db") as gs:
        gs.build(ss)
        assert shared_files(gs) == {"count": 0, "files": []}
