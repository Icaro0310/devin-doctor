"""Extraction tests — the fixture encodes exact expected node/edge counts."""

import pytest
from devin_internals.parsers import SessionsStore

from devin_graph.extract import (
    extract_all,
    extract_paths,
    extract_session,
    extract_tool_name,
    normalize_path,
    parse_payload,
)

from conftest import ALPHA, BETA


# -- path normalization ------------------------------------------------------


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("/a/b/c.py", "/a/b/c.py"),
        ("\\repo\\x\\y.py", "/repo/x/y.py"),
        ("C:\\Users\\me\\f.py", "C:/Users/me/f.py"),
        ("/a//b/./c.py", "/a/b/c.py"),
        ('"/quoted/p.py"', "/quoted/p.py"),
        ("rel/dir/", "rel/dir"),
        ("  /spaced/f.py  ", "/spaced/f.py"),
    ],
)
def test_normalize_path(raw, expected):
    assert normalize_path(raw) == expected


def test_normalize_path_rejects_garbage():
    assert normalize_path("") is None
    assert normalize_path("   ") is None
    assert normalize_path(None) is None


# -- payload parsing (unstable format → defensive) ---------------------------


def test_parse_payload_tolerates_junk():
    assert parse_payload(None) is None
    assert parse_payload("") is None
    assert parse_payload("not json") is None
    assert parse_payload("[1, 2]") is None
    assert parse_payload('{"kind": "read"}') == {"kind": "read"}


# -- tool name ---------------------------------------------------------------


def test_tool_name_priority():
    assert extract_tool_name({"name": "n", "kind": "k"}) == "n"
    assert extract_tool_name({"tool_name": "tn", "kind": "k"}) == "tn"
    assert extract_tool_name({"tool": "t", "kind": "k"}) == "t"
    assert extract_tool_name({"kind": "read"}) == "read"
    assert extract_tool_name({"title": "Run command"}) == "Run command"


def test_tool_name_nested_and_missing():
    assert extract_tool_name({"rawInput": {"tool": "shell"}}) == "shell"
    assert extract_tool_name({"kind": 42}) is None
    assert extract_tool_name({}) is None


# -- path extraction from tool-call payloads ---------------------------------


def test_paths_from_file_keys_and_locations():
    payload = {
        "kind": "read",
        "rawInput": {"file_path": "/x/a.py"},
        "locations": [{"path": "/x/b.py"}],
    }
    assert extract_paths(payload) == {"/x/a.py", "/x/b.py"}


def test_paths_from_list_value():
    payload = {"tool": "fs_write", "args": {"files": ["d/r.md", "d/n.txt"]}}
    assert extract_paths(payload) == {"d/r.md", "d/n.txt"}


def test_paths_from_command_string():
    payload = {
        "kind": "execute",
        "rawInput": {"command": "python -m pytest tests/test_app.py -x"},
    }
    assert extract_paths(payload) == {"tests/test_app.py"}


def test_paths_command_skips_urls_and_flags():
    payload = {
        "command": "curl https://example.com/x.py && git commit -m wip --amend",
    }
    assert extract_paths(payload) == set()


def test_paths_dedup_and_ignore_nonstrings():
    payload = {"path": "/a.py", "other": {"path": "/a.py"}, "n": 3}
    assert extract_paths(payload) == {"/a.py"}


# -- per-session extraction --------------------------------------------------


def _by_kind(extraction, kind):
    return sorted(n.key for n in extraction.nodes if n.kind == kind)


def _edge_set(extraction, kind):
    return {(e.src, e.dst) for e in extraction.edges if e.kind == kind}


def test_extract_session_structure(sessions_db):
    with SessionsStore(sessions_db) as store:
        sess = next(s for s in store.sessions() if s.id == "sess-a")
        calls = store.tool_call_state("sess-a")
    ex = extract_session(sess, calls)

    assert ("session", "sess-a") in {(n.kind, n.key) for n in ex.nodes}
    assert ("project", ALPHA) in {(n.kind, n.key) for n in ex.nodes}
    assert _by_kind(ex, "tool") == ["execute", "read"]
    assert _by_kind(ex, "tool_call") == [
        "sess-a:sess-a-tc0", "sess-a:sess-a-tc1", "sess-a:sess-a-tc2"]
    assert _by_kind(ex, "file") == [
        f"{ALPHA}/src/app.py", f"{ALPHA}/tests/test_app.py"]

    assert _edge_set(ex, "runs_in") == {
        (("session", "sess-a"), ("project", ALPHA))}
    assert _edge_set(ex, "made_call") == {
        (("session", "sess-a"), ("tool_call", f"sess-a:sess-a-tc{i}"))
        for i in range(3)
    }
    # tc2 has NULL payload → made_call exists but no call_used/file_touched.
    assert _edge_set(ex, "call_used") == {
        (("tool_call", "sess-a:sess-a-tc0"), ("tool", "read")),
        (("tool_call", "sess-a:sess-a-tc1"), ("tool", "execute")),
    }
    assert _edge_set(ex, "tool_used") == {
        (("session", "sess-a"), ("tool", "read")),
        (("session", "sess-a"), ("tool", "execute")),
    }
    assert _edge_set(ex, "file_touched") == {
        (("tool_call", "sess-a:sess-a-tc0"), ("file", f"{ALPHA}/src/app.py")),
        (("tool_call", "sess-a:sess-a-tc1"),
         ("file", f"{ALPHA}/tests/test_app.py")),
    }


def test_extract_session_relative_paths_resolve_to_cwd(sessions_db):
    """docs/README.md is written relative to sess-c's cwd (/repo/alpha)."""
    with SessionsStore(sessions_db) as store:
        sess = next(s for s in store.sessions() if s.id == "sess-c")
        calls = store.tool_call_state("sess-c")
    ex = extract_session(sess, calls)
    assert _by_kind(ex, "file") == [
        f"{ALPHA}/docs/README.md", f"{ALPHA}/docs/notes.txt"]


def test_call_payload_wins_over_update(sessions_db):
    """tool_call_json is authoritative over tool_call_update_json."""
    import sqlite3
    import json as j
    con = sqlite3.connect(sessions_db)
    with con:
        con.execute(
            "UPDATE tool_call_state SET tool_call_update_json = ?"
            " WHERE session_id = 'sess-a' AND tool_call_id = 'sess-a-tc0'",
            (j.dumps({"kind": "tool_call_update"}),))
    con.close()
    with SessionsStore(sessions_db) as store:
        sess = next(s for s in store.sessions() if s.id == "sess-a")
        calls = store.tool_call_state("sess-a")
    ex = extract_session(sess, calls)
    assert _edge_set(ex, "call_used") == {
        (("tool_call", "sess-a:sess-a-tc0"), ("tool", "read")),
        (("tool_call", "sess-a:sess-a-tc1"), ("tool", "execute")),
    }


def test_extract_all_counts(sessions_db):
    with SessionsStore(sessions_db) as store:
        ex = extract_all(store)

    counts = {}
    for n in ex.nodes:
        counts[n.kind] = counts.get(n.kind, 0) + 1
    assert counts == {
        "session": 3, "project": 2, "tool": 4, "tool_call": 6, "file": 5}

    ecounts = {}
    for e in ex.edges:
        ecounts[e.kind] = ecounts.get(e.kind, 0) + 1
    assert ecounts == {
        "runs_in": 3, "made_call": 6, "call_used": 5,
        "tool_used": 5, "file_touched": 6}


def test_extract_all_dedupes_shared_nodes(sessions_db):
    """/repo/alpha/src/app.py is touched by sess-a and sess-b → one file node,
    and both projects share the 'read' tool → one tool node."""
    with SessionsStore(sessions_db) as store:
        ex = extract_all(store)
    files = [n for n in ex.nodes if n.kind == "file"]
    assert sum(1 for n in files if n.key == f"{ALPHA}/src/app.py") == 1
    reads = [n for n in ex.nodes if n.kind == "tool" and n.key == "read"]
    assert len(reads) == 1


def test_session_node_attrs(sessions_db):
    with SessionsStore(sessions_db) as store:
        sess = next(s for s in store.sessions() if s.id == "sess-a")
        calls = store.tool_call_state("sess-a")
    ex = extract_session(sess, calls)
    node = next(n for n in ex.nodes if n.kind == "session")
    assert node.attrs["title"] == "Alpha work"
    assert node.attrs["model"] == "fixture-model"
    assert node.attrs["hidden"] is False
