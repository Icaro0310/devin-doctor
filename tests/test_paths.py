from pathlib import Path

from devin_doctor.paths import default_config_dir, default_data_dir, locate_stores


def test_linux_discovers_cli_data_and_desktop_config_separately(tmp_path):
    data_home = tmp_path / "data"
    config_home = tmp_path / "config"
    data_dir = data_home / "devin"
    config_dir = config_home / "Devin"
    acp_dir = config_dir / "User" / "acp-messages"
    state_db = config_dir / "User" / "globalStorage" / "state.vscdb"
    (data_dir / "cli").mkdir(parents=True)
    acp_dir.mkdir(parents=True)
    state_db.parent.mkdir(parents=True)
    (data_dir / "cli" / "sessions.db").touch()
    state_db.touch()
    env = {"XDG_DATA_HOME": str(data_home), "XDG_CONFIG_HOME": str(config_home)}

    assert default_data_dir(environ=env, platform="linux") == data_dir
    assert default_config_dir(environ=env, platform="linux") == config_dir
    stores = locate_stores(data_dir, config_dir=config_dir)
    assert stores.sessions_db == data_dir / "cli" / "sessions.db"
    assert stores.acp_dir == acp_dir
    assert stores.state_vscdb == state_db


def test_legacy_colocated_store_layout_still_works(tmp_path):
    root = tmp_path / "legacy-devin"
    (root / "User" / "acp-messages").mkdir(parents=True)
    (root / "cli").mkdir(parents=True)

    stores = locate_stores(root)

    assert stores.acp_dir == root / "User" / "acp-messages"
    assert stores.sessions_db == root / "cli" / "sessions.db"
