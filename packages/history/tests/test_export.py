import hashlib
import json

from conftest import add_session, msg
from devin_history.export import export_sessions
from devin_internals.parsers import SessionsStore


def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_export_one_note_per_session_plus_index(store, tmp_path):
    out = tmp_path / "out"
    res = export_sessions(store, out)

    assert len(res.written) == 3
    assert res.skipped_empty == []
    notes = sorted(p.name for p in out.glob("*.md") if p.name != "index.md")
    assert notes == sorted(res.written)
    assert (out / "index.md").exists()
    for name in res.written:
        body = (out / name).read_text(encoding="utf-8")
        assert "session_id:" in body
        assert "last_activity:" in body
        assert "## Conversation" in body


def test_export_rerun_is_idempotent(store, tmp_path):
    out = tmp_path / "out"
    export_sessions(store, out)
    before = {p.name: p.stat().st_mtime_ns for p in out.iterdir()}

    res = export_sessions(store, out)
    assert res.written == []
    assert len(res.skipped_unchanged) == 3
    after = {p.name: p.stat().st_mtime_ns for p in out.iterdir()}
    assert before == after


def test_export_force_rewrites(store, tmp_path):
    out = tmp_path / "out"
    export_sessions(store, out)
    res = export_sessions(store, out, force=True)
    assert len(res.written) == 3
    assert res.skipped_unchanged == []


def test_export_skips_empty_and_no_user_sessions(db_path, tmp_path):
    add_session(db_path, "empty-1", messages=[])
    add_session(db_path, "agent-only", messages=[msg("agent", "hi"), msg("agent", "yo")])
    with SessionsStore(db_path) as store:
        res = export_sessions(store, tmp_path / "out")
    assert set(res.skipped_empty) == {"empty-1", "agent-only"}
    assert len(res.index_entries) == 3


def test_export_dry_run_writes_nothing(store, tmp_path):
    out = tmp_path / "out"
    res = export_sessions(store, out, dry_run=True)
    assert len(res.written) == 3
    assert not out.exists() or list(out.iterdir()) == []


def test_export_index_md_has_stats_block(store, tmp_path):
    out = tmp_path / "out"
    res = export_sessions(store, out)
    index = (out / "index.md").read_text(encoding="utf-8")

    assert index.startswith("---\ntags:")
    assert "## Stats" in index
    assert "| Project | Sessions | User | Assistant | Tool |" in index
    assert f"| **Total** | **{len(res.index_entries)}** |" in index
    assert "**Span:**" in index and "**Formats:** md:" in index

    total_user = sum(e.user_msgs for e in res.index_entries)
    assert total_user > 0
    assert f"**{total_user}**" in index  # bolded in the Total row
    for project in {e.project for e in res.index_entries}:
        assert f"| {project} | " in index


def test_export_index_json_has_stats(store, tmp_path):
    out = tmp_path / "json"
    res = export_sessions(store, out, fmt="json")
    index = json.loads((out / "index.json").read_text(encoding="utf-8"))

    stats = index["stats"]
    assert stats["total"] == 3
    assert stats["formats"] == {"json": 3}
    assert stats["date_first"] <= stats["date_last"]
    msgs = stats["messages"]
    assert msgs["user"] == sum(e.user_msgs for e in res.index_entries)
    assert msgs["assistant"] == sum(
        e.assistant_msgs for e in res.index_entries)
    assert msgs["tool"] == sum(e.tool_msgs for e in res.index_entries)
    assert set(stats["projects"]) == {e.project for e in res.index_entries}


def test_export_index_stats_include_unchanged_sessions(store, tmp_path):
    out = tmp_path / "out"
    export_sessions(store, out)
    res = export_sessions(store, out)  # all unchanged this time
    index = (out / "index.md").read_text(encoding="utf-8")
    assert f"| **Total** | **{len(res.index_entries)}** |" in index
    stats_total = sum(e.user_msgs for e in res.index_entries)
    assert stats_total > 0


def test_export_json_dump(store, tmp_path):
    out = tmp_path / "json"
    res = export_sessions(store, out, fmt="json")
    assert len(res.written) == 3
    assert (out / "index.json").exists()
    data = json.loads((out / res.written[0]).read_text(encoding="utf-8"))
    assert data["session_id"]
    assert data["messages"]
    assert data["last_activity"]
    index = json.loads((out / "index.json").read_text(encoding="utf-8"))
    assert len(index["sessions"]) == 3


def test_export_json_rerun_idempotent(store, tmp_path):
    out = tmp_path / "json"
    export_sessions(store, out, fmt="json")
    res = export_sessions(store, out, fmt="json")
    assert res.written == []
    assert len(res.skipped_unchanged) == 3


def test_export_does_not_modify_source_db(db_path, tmp_path):
    before = _sha256(db_path)
    with SessionsStore(db_path) as store:
        export_sessions(store, tmp_path / "out")
        export_sessions(store, tmp_path / "json", fmt="json")
    assert _sha256(db_path) == before
    assert not list(db_path.parent.glob("sessions.db-*"))
