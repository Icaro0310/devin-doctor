"""Milestones: ``milestone:`` session titles + per-project milestones.json."""

from __future__ import annotations

import json

import pytest
from devin_pm.milestones import (
    MilestonesError,
    collect_milestones,
    detect_milestones,
    done_fraction,
    load_milestones,
    milestones_path,
)
from devin_pm.projects import group_sessions, load_sessions


@pytest.fixture
def projects(sessions_db):
    return {p.name: p for p in group_sessions(load_sessions(sessions_db))}


def test_detect_milestone_from_session_title(sessions_db):
    sessions = load_sessions(sessions_db)
    found = {m.name: m for m in detect_milestones(sessions)}
    assert set(found) == {"Alpha scaffold", "Beta MVP"}
    # hidden session → done; active session → pending
    assert found["Alpha scaffold"].done is True
    assert found["Beta MVP"].done is False
    assert found["Alpha scaffold"].session_id == "a-2"
    assert found["Beta MVP"].session_id == "b-1"


def test_milestones_path_is_project_root(projects):
    path = milestones_path(projects["alpha"])
    assert path.name == "milestones.json"
    assert path.parent.name == "alpha"


def test_load_milestones_missing_file(projects):
    assert load_milestones(milestones_path(projects["alpha"])) == []


def test_load_milestones_file(projects, workdir):
    (workdir / "alpha" / "milestones.json").write_text(
        json.dumps(
            {
                "milestones": [
                    {"name": "M1 — core", "done": True},
                    {"name": "M2 — polish", "done": False},
                    "M3 — stretch",
                ]
            }
        ),
        encoding="utf-8",
    )
    ms = load_milestones(milestones_path(projects["alpha"]))
    assert [(m.name, m.done) for m in ms] == [
        ("M1 — core", True),
        ("M2 — polish", False),
        ("M3 — stretch", False),
    ]
    assert all(m.source == "file" for m in ms)


def test_load_milestones_accepts_bare_list(projects, workdir):
    (workdir / "alpha" / "milestones.json").write_text(
        json.dumps([{"name": "X", "done": True}]), encoding="utf-8"
    )
    ms = load_milestones(milestones_path(projects["alpha"]))
    assert [(x.name, x.done) for x in ms] == [("X", True)]


def test_load_milestones_malformed(projects, workdir):
    bad = workdir / "alpha" / "milestones.json"
    bad.write_text("{nope", encoding="utf-8")
    with pytest.raises(MilestonesError):
        load_milestones(milestones_path(projects["alpha"]))


def test_collect_merges_file_and_detected(projects, workdir):
    """File entries win on name collision; detected ones fill the rest."""
    (workdir / "alpha" / "milestones.json").write_text(
        json.dumps(
            {
                "milestones": [
                    {"name": "Alpha scaffold", "done": False},  # overrides session
                    {"name": "Alpha launch", "done": False},
                ]
            }
        ),
        encoding="utf-8",
    )
    ms = {m.name: m for m in collect_milestones(projects["alpha"])}
    assert ms["Alpha scaffold"].done is False  # file wins over hidden session
    assert ms["Alpha scaffold"].source == "file"
    assert ms["Alpha launch"].done is False


def test_collect_detected_only(projects):
    ms = {m.name: m for m in collect_milestones(projects["beta"])}
    assert list(ms) == ["Beta MVP"]
    assert ms["Beta MVP"].done is False


def test_done_fraction(projects, workdir):
    (workdir / "alpha" / "milestones.json").write_text(
        json.dumps({"milestones": [{"name": "L", "done": False}]}),
        encoding="utf-8",
    )
    ms = collect_milestones(projects["alpha"])
    # "L" (file, pending) + "Alpha scaffold" (session-detected, hidden → done)
    assert done_fraction(ms) == (1, 2, 50.0)

    ms_beta = collect_milestones(projects["beta"])
    assert done_fraction(ms_beta) == (0, 1, 0.0)

    assert done_fraction([]) == (0, 0, 0.0)


def test_done_fraction_counts(projects):
    """Detected-only: alpha has 1 done of 1 → 100%."""
    ms = collect_milestones(projects["alpha"])
    done, total, pct = done_fraction(ms)
    assert (done, total) == (1, 1)
    assert pct == 100.0
