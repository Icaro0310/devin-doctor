

def test_plan_emits_steps_and_nothing_executed(data_dir, tmp_path, capsys):
    from devin_doctor.cli import main
    assert main(["plan", "--data-dir", str(data_dir),
                 "--cwd", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "nothing below was executed" in out


def test_plan_json(data_dir, tmp_path, capsys):
    import json
    from devin_doctor.cli import main
    assert main(["plan", "--data-dir", str(data_dir),
                 "--cwd", str(tmp_path), "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert "steps" in data and "overall" in data
