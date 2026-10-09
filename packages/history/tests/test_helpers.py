import json

from devin_history.messages import first_user_text, parse_chat_message, parse_nodes
from devin_history.paths import default_sessions_db
from devin_history.times import duration_minutes, fmt_ts, to_seconds


def test_parse_fixture_shape_agent_maps_to_assistant():
    m = parse_chat_message(json.dumps({"role": "agent", "text": "hi there"}))
    assert m is not None
    assert m.role == "assistant"
    assert m.text == "hi there"


def test_parse_content_key_shape():
    m = parse_chat_message(json.dumps({"role": "user", "content": "hello"}))
    assert m.role == "user"
    assert m.text == "hello"


def test_parse_content_block_list():
    payload = {
        "role": "assistant",
        "content": [{"content": {"text": "a"}}, {"text": "b"}, "c"],
    }
    m = parse_chat_message(json.dumps(payload))
    assert m.text == "a\nb\nc"


def test_parse_rejects_non_dict_json():
    assert parse_chat_message("{not json") is None
    assert parse_chat_message("[1,2,3]") is None
    assert parse_chat_message('"just a string"') is None


def test_parse_nodes_skips_unparsable(store):
    nodes = store.message_nodes()
    msgs = parse_nodes(nodes)
    assert len(msgs) == len(nodes)
    assert {m.role for m in msgs} == {"user", "assistant"}


def test_first_user_text_collapses_whitespace():
    msgs = parse_nodes([json.dumps({"role": "user", "content": "line\n  two"})])
    assert first_user_text(msgs) == "line two"


def test_to_seconds_handles_ms_and_s():
    assert to_seconds(1_780_000_000_000) == 1_780_000_000.0
    assert to_seconds(1_780_000_000) == 1_780_000_000.0
    assert to_seconds(None) == 0.0


def test_fmt_ts_renders_ms():
    assert fmt_ts(1_780_000_000_000).startswith("2026-")
    assert fmt_ts(0) == ""


def test_duration_minutes_ms_and_s():
    assert duration_minutes(1_780_000_000_000, 1_780_000_000_000 + 120_000) == 2.0
    assert duration_minutes(1_780_000_000, 1_780_000_000 + 120) == 2.0


def test_default_sessions_db_windows(monkeypatch, tmp_path):
    db = tmp_path / "devin" / "cli" / "sessions.db"
    db.parent.mkdir(parents=True)
    db.write_bytes(b"x")
    monkeypatch.setattr("devin_history.paths.sys.platform", "win32")
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setattr("devin_history.paths.Path.home", lambda: tmp_path / "nohome")
    found = default_sessions_db()
    assert found is not None and found.name == "sessions.db"


def test_default_sessions_db_missing(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path / "empty"))
    monkeypatch.setattr("devin_history.paths.Path.home", lambda: tmp_path / "nohome")
    assert default_sessions_db() is None
