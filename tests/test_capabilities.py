"""capabilities command: profile resolution precedence, local probing and
the opt-in --probe-network flag."""

import json
import os

from devin_doctor import capabilities
from devin_doctor.cli import main


def _collect(env=None, config_dir=None, platform="linux"):
    env = {} if env is None else env
    return capabilities.collect_profile(
        config_dir=config_dir, environ=env, platform=platform
    )


def test_default_profile_is_corporate(tmp_path):
    profile = _collect(config_dir=tmp_path)
    assert profile["profile"] == "corporate"
    assert profile["capabilities"]["daemon"] is False
    assert profile["capabilities"]["multi-host"] is False


def test_env_var_declares_personal(tmp_path):
    profile = _collect(
        env={"DEVIN_ECOSYSTEM_PROFILE": "personal"}, config_dir=tmp_path
    )
    assert profile["profile"] == "personal"
    assert profile["capabilities"]["daemon"] is True


def test_profile_file_declares_personal(tmp_path):
    (tmp_path / "devin-profile.json").write_text(
        '{"profile": "personal"}', "utf-8"
    )
    profile = _collect(config_dir=tmp_path)
    assert profile["profile"] == "personal"


def test_env_var_beats_profile_file(tmp_path):
    (tmp_path / "devin-profile.json").write_text(
        '{"profile": "personal"}', "utf-8"
    )
    profile = _collect(
        env={"DEVIN_ECOSYSTEM_PROFILE": "corporate"}, config_dir=tmp_path
    )
    assert profile["profile"] == "corporate"


def test_invalid_env_value_falls_through(tmp_path):
    (tmp_path / "devin-profile.json").write_text(
        '{"profile": "personal"}', "utf-8"
    )
    profile = _collect(
        env={"DEVIN_ECOSYSTEM_PROFILE": "bogus"}, config_dir=tmp_path
    )
    assert profile["profile"] == "personal"


def test_invalid_profile_file_ignored(tmp_path):
    (tmp_path / "devin-profile.json").write_text("{broken", "utf-8")
    profile = _collect(config_dir=tmp_path)
    assert profile["profile"] == "corporate"


def test_net_keys_unknown_without_probe(tmp_path):
    profile = _collect(config_dir=tmp_path)
    assert profile["capabilities"]["net.outbound"] == "unknown"
    assert profile["capabilities"]["net.listener"] == "unknown"


def test_scheduler_true_when_crontab_on_path(tmp_path):
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    (fake_bin / "crontab").write_text("#!/bin/sh\n", "utf-8")
    (fake_bin / "crontab").chmod(0o755)
    env = {"PATH": str(fake_bin)}
    profile = _collect(env=env, config_dir=tmp_path)
    assert profile["capabilities"]["scheduler"] is True


def test_scheduler_false_without_scheduler_binaries(tmp_path):
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    env = {"PATH": str(fake_bin)}
    profile = _collect(env=env, config_dir=tmp_path, platform="win32")
    assert profile["capabilities"]["scheduler"] is False


def test_containers_and_llm_from_path(tmp_path):
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    for name in ("docker", "ollama"):
        p = fake_bin / name
        p.write_text("#!/bin/sh\n", "utf-8")
        p.chmod(0o755)
    env = {"PATH": str(fake_bin)}
    profile = _collect(env=env, config_dir=tmp_path)
    assert profile["capabilities"]["containers"] is True
    assert profile["capabilities"]["llm.local"] is True


def test_llm_local_from_env(tmp_path):
    profile = _collect(env={"OLLAMA_HOST": "127.0.0.1:11434"},
                       config_dir=tmp_path)
    assert profile["capabilities"]["llm.local"] is True


def test_comms_from_env_token(tmp_path):
    profile = _collect(env={"SLACK_BOT_TOKEN": "x"}, config_dir=tmp_path)
    assert profile["capabilities"]["comms"] is True


def test_output_shape_keys(tmp_path):
    profile = _collect(config_dir=tmp_path)
    assert set(profile) == {"profile", "capabilities"}
    assert set(profile["capabilities"]) == {
        "scheduler",
        "daemon",
        "net.outbound",
        "net.listener",
        "llm.local",
        "comms",
        "containers",
        "proxy",
        "ram.heavy",
        "multi-host",
    }


def test_cli_capabilities_exit_0_and_json(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("DEVIN_ECOSYSTEM_PROFILE", raising=False)
    rc = main(["capabilities", "--config-dir", str(tmp_path)])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["profile"] in ("corporate", "personal")
    assert payload["capabilities"]["net.outbound"] == "unknown"
