import hashlib
import json

from devin_history.export import export_sessions
from devin_internals.parsers import SessionsStore

from conftest import add_session, msg


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
