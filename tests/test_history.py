"""SE-2: link search hits to devin-history export notes.

devin-history writes ``<YYYY-MM-DD>_<session-id>.md`` (or ``.json``) in its
export dir. ``--history-dir`` attaches that note's path to each hit whose
session has one — missing notes are simply unlinked, never an error.
"""

import json

from devin_search.cli import main
from devin_search.history import attach_history_notes, history_note
from devin_search.index import build_index
from devin_search.query import search

from conftest import add_session, msg


def _note(directory, session_id, date="2026-05-28", ext="md", body="# note\n"):
    path = directory / f"{date}_{session_id}.{ext}"
    path.write_text(body, encoding="utf-8")
    return path


def test_history_note_finds_md(tmp_path):
    note = _note(tmp_path, "sess-1")
    assert history_note(tmp_path, "sess-1") == note


def test_history_note_prefers_md_over_json(tmp_path):
    md = _note(tmp_path, "sess-1", ext="md")
    _note(tmp_path, "sess-1", ext="json", body="{}")
    assert history_note(tmp_path, "sess-1") == md


def test_history_note_json_fallback(tmp_path):
    js = _note(tmp_path, "sess-1", ext="json", body="{}")
    assert history_note(tmp_path, "sess-1") == js


def test_history_note_missing_returns_none(tmp_path):
    assert history_note(tmp_path, "sess-zzz") is None
    assert history_note(tmp_path / "nope", "sess-1") is None


def test_history_note_does_not_cross_match(tmp_path):
    # Suffix matching must not confuse "sess-1" with "xsess-1".
    _note(tmp_path, "xsess-1")
    assert history_note(tmp_path, "sess-1") is None


def test_attach_history_notes(db_path, tmp_path):
    add_session(
        db_path,
        "sess-1",
        messages=[msg("user", "flibberty deploy notes")],
    )
    idx = tmp_path / "search.db"
    build_index(idx, sessions_db=db_path)
    hits = search(idx, "flibberty")
    assert hits and all(h.history_note is None for h in hits)

    hist = tmp_path / "history"
    hist.mkdir()
    note = _note(hist, "sess-1")
    linked = attach_history_notes(hits, hist)
    assert all(h.history_note == str(note) for h in linked)

    # A session without a note stays unlinked — no error.
    add_session(
        db_path,
        "sess-2",
        messages=[msg("user", "flibberty elsewhere")],
    )
    build_index(idx, sessions_db=db_path)
    hits = search(idx, "flibberty")
    linked = attach_history_notes(hits, hist)
    by_sid = {h.session_id: h.history_note for h in linked}
    assert by_sid["sess-1"] == str(note)
    assert by_sid["sess-2"] is None

    # Missing dir → hits pass through untouched.
    assert attach_history_notes(hits, tmp_path / "gone") == list(hits)


def test_cli_query_history_dir_text(db_path, tmp_path, capsys):
    add_session(
        db_path, "sess-9", messages=[msg("user", "xyzzy cli marker")]
    )
    idx = tmp_path / "search.db"
    hist = tmp_path / "history"
    hist.mkdir()
    note = _note(hist, "sess-9")
    main(["index", "--sessions-db", str(db_path), "--no-acp", "--index", str(idx)])
    capsys.readouterr()

    rc = main(
        ["query", "xyzzy", "--index", str(idx), "--history-dir", str(hist)]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert f"note: {note}" in out


def test_cli_query_history_dir_json(db_path, tmp_path, capsys):
    add_session(
        db_path, "sess-9", messages=[msg("user", "xyzzy cli marker")]
    )
    idx = tmp_path / "search.db"
    hist = tmp_path / "history"
    hist.mkdir()
    note = _note(hist, "sess-9")
    main(["index", "--sessions-db", str(db_path), "--no-acp", "--index", str(idx)])
    capsys.readouterr()

    rc = main(
        [
            "query", "xyzzy", "--index", str(idx),
            "--history-dir", str(hist), "--json",
        ]
    )
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["hits"][0]["history_note"] == str(note)


def test_cli_query_history_dir_without_flag_null(db_path, tmp_path, capsys):
    add_session(
        db_path, "sess-9", messages=[msg("user", "xyzzy cli marker")]
    )
    idx = tmp_path / "search.db"
    main(["index", "--sessions-db", str(db_path), "--no-acp", "--index", str(idx)])
    capsys.readouterr()
    rc = main(["query", "xyzzy", "--index", str(idx), "--json"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["hits"][0]["history_note"] is None
