import json

import pytest
from devin_history.cli import main
from devin_internals.fixtures import create_sessions_db


def test_cli_list_table(db_path, capsys):
    assert main(["list", "--sessions-db", str(db_path)]) == 0
    out = capsys.readouterr().out
    assert "CREATED" in out
    assert out.count("fixture-model") == 3
    assert "Fixture session" in out


def test_cli_list_json_shape(db_path, capsys):
    assert main(["list", "--sessions-db", str(db_path), "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert len(data["sessions"]) == 3
    row = data["sessions"][0]
    assert {"id", "title", "project", "created_at", "last_activity",
            "duration_min"} <= set(row)


def test_cli_list_limit(db_path, capsys):
    assert main(["list", "--sessions-db", str(db_path), "--limit", "1"]) == 0
    out = capsys.readouterr().out
    assert out.count("fixture-model") == 1


def test_cli_export_md(db_path, tmp_path, capsys):
    out = tmp_path / "notes"
    assert main(["export", "--sessions-db", str(db_path),
                 "--out", str(out)]) == 0
    assert len(list(out.glob("2*.md"))) == 3
    assert (out / "index.md").exists()
    assert "written: 3" in capsys.readouterr().out


def test_cli_export_json_output(db_path, tmp_path, capsys):
    out = tmp_path / "dump"
    assert main(["export", "--sessions-db", str(db_path), "--out", str(out),
                 "--format", "json", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["format"] == "json"
    assert len(data["written"]) == 3


def test_cli_export_dry_run(db_path, tmp_path, capsys):
    out = tmp_path / "notes"
    assert main(["export", "--sessions-db", str(db_path), "--out", str(out),
                 "--dry-run"]) == 0
    assert "would write: 3" in capsys.readouterr().out
    assert not (out / "index.md").exists()


def test_cli_audit_markdown_and_csv(db_path, tmp_path, capsys):
    csv_path = tmp_path / "audit.csv"
    assert main(["audit", "--sessions-db", str(db_path),
                 "--csv", str(csv_path)]) == 0
    out = capsys.readouterr().out
    assert "# Session audit" in out
    assert "## Anomalies" in out
    assert csv_path.exists()
    assert len(csv_path.read_text(encoding="utf-8").splitlines()) == 4


def test_cli_audit_json(db_path, capsys):
    assert main(["audit", "--sessions-db", str(db_path), "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["schema_version"] == 17
    assert data["summary"]["total"] == 3
    assert "anomalies" in data


def test_cli_unknown_schema_fails_loud(tmp_path, capsys):
    bad = create_sessions_db(tmp_path / "future.db", schema_version=18)
    with pytest.raises(SystemExit) as exc:
        main(["list", "--sessions-db", str(bad)])
    assert exc.value.code == 2
    assert "schema version" in capsys.readouterr().err


def test_cli_missing_db_fails(tmp_path, capsys):
    with pytest.raises(SystemExit) as exc:
        main(["list", "--sessions-db", str(tmp_path / "nope.db")])
    assert exc.value.code == 2
    assert "no such file" in capsys.readouterr().err


def test_cli_no_default_db(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("APPDATA", str(tmp_path / "empty"))
    monkeypatch.setattr(
        "devin_history.paths.Path.home", lambda: tmp_path / "nohome")
    with pytest.raises(SystemExit) as exc:
        main(["list"])
    assert exc.value.code == 2
    assert "no sessions.db found" in capsys.readouterr().err


def test_cli_never_writes_source_db(db_path, tmp_path, capsys):
    import hashlib
    before = hashlib.sha256(db_path.read_bytes()).hexdigest()
    main(["list", "--sessions-db", str(db_path)])
    main(["export", "--sessions-db", str(db_path), "--out", str(tmp_path / "o")])
    main(["audit", "--sessions-db", str(db_path), "--json"])
    capsys.readouterr()
    assert hashlib.sha256(db_path.read_bytes()).hexdigest() == before
