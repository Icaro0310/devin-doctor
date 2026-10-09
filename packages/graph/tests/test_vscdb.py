"""GR-1: state.vscdb extraction → gui_session/gui_workspace."""

import json
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from devin_graph.vscdb import extract_vscdb


def _vscdb(path):
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE ItemTable(key TEXT PRIMARY KEY, value TEXT)")
    con.execute("INSERT INTO ItemTable VALUES (?, ?)", (
        "windsurfSpace.sessionWorkspace/acp/devin-cli/canyon-newspaper",
        json.dumps({"workspaceId": "/w/repo", "label": "repo",
                    "folders": ["/w/repo"], "lastUpdated": 1234})))
    con.execute("INSERT INTO ItemTable VALUES (?, ?)", (
        "windsurfSpace.resourceToSpace",
        json.dumps({"sp1": ["vscode-cascade-editor:///cascade-acp/devin-cli/canyon-newspaper"]})))
    con.execute("INSERT INTO ItemTable VALUES (?, ?)", (
        "windsurfSpace.metadata",
        json.dumps({"sp1": {"lastAccessed": 9999}})))
    con.execute("INSERT INTO ItemTable VALUES ('unrelated.key', '{}')")
    con.commit(); con.close()


def test_extract_vscdb(tmp_path):
    db = tmp_path / "state.vscdb"; _vscdb(db)
    ex = extract_vscdb(db)
    gs = [n for n in ex.nodes if n.kind == "gui_session"]
    assert len(gs) == 1 and gs[0].key == "canyon-newspaper"
    assert gs[0].attrs["space_id"] == "sp1"
    assert gs[0].attrs["lastAccessed"] == 9999
    assert gs[0].attrs["label"] == "repo"
    assert any(e.kind == "gui_workspace" and e.dst == ("project", "/w/repo")
               for e in ex.edges)


def test_extract_malformed_skipped(tmp_path):
    db = tmp_path / "state.vscdb"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE ItemTable(key TEXT PRIMARY KEY, value TEXT)")
    con.execute("INSERT INTO ItemTable VALUES (?, 'not-json')",
                ("windsurfSpace.sessionWorkspace/acp/x/bad-slug",))
    con.commit(); con.close()
    ex = extract_vscdb(db)
    assert len(ex.nodes) == 1  # node created with null attrs
    assert not ex.edges        # no workspace → no edge


def test_not_a_vscdb(tmp_path):
    db = tmp_path / "state.vscdb"
    db.write_bytes(b"junk")
    with pytest.raises(ValueError):
        extract_vscdb(db)


def test_build_merges_gui_coverage(tmp_path, sessions_db):
    """CLI build --vscdb adds gui_session nodes under the 'vscdb' owner."""
    from devin_graph.cli import main
    from devin_graph.store import GraphStore
    vdb = tmp_path / "state.vscdb"; _vscdb(vdb)
    gdb = tmp_path / "graph.db"
    assert main(["build", "--sessions-db", str(sessions_db),
                 "--vscdb", str(vdb), "--graph", str(gdb)]) == 0
    with GraphStore(gdb) as gs:
        kinds = {n.kind for n in gs.nodes()}
    assert "gui_session" in kinds
