from pathlib import Path

from devin_graph.paths import default_sessions_db, sessions_db_candidates


def test_linux_prefers_xdg_data_home_and_keeps_legacy_fallback(tmp_path):
    env = {
        "XDG_DATA_HOME": str(tmp_path / "data"),
        "XDG_CONFIG_HOME": str(tmp_path / "config"),
    }
    data_db = Path(env["XDG_DATA_HOME"]) / "devin" / "cli" / "sessions.db"
    legacy_db = Path(env["XDG_CONFIG_HOME"]) / "devin" / "cli" / "sessions.db"
    data_db.parent.mkdir(parents=True)
    legacy_db.parent.mkdir(parents=True)
    data_db.touch()
    legacy_db.touch()

    assert sessions_db_candidates(environ=env, platform="linux")[0] == data_db
    assert default_sessions_db(environ=env, platform="linux") == data_db


def test_linux_uses_legacy_xdg_config_when_data_store_is_absent(tmp_path):
    env = {
        "XDG_DATA_HOME": str(tmp_path / "data"),
        "XDG_CONFIG_HOME": str(tmp_path / "config"),
    }
    legacy_db = Path(env["XDG_CONFIG_HOME"]) / "devin" / "cli" / "sessions.db"
    legacy_db.parent.mkdir(parents=True)
    legacy_db.touch()

    assert default_sessions_db(environ=env, platform="linux") == legacy_db
