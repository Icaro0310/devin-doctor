"""Markdown status reports: per project and global."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from devin_pm.milestones import collect_milestones
from devin_pm.projects import group_sessions, load_sessions
from devin_pm.report import (
    render_global_report,
    render_project_report,
    render_status_table,
)

from conftest import BASE_TS_MS


def _d(offset_ms: int = 0) -> str:
    return (
        datetime.fromtimestamp((BASE_TS_MS + offset_ms) / 1000, tz=timezone.utc)
        .strftime("%Y-%m-%d")
    )


@pytest.fixture
def projects(sessions_db):
    return {p.name: p for p in group_sessions(load_sessions(sessions_db))}


def test_status_table_has_header_and_rows(projects):
    table = render_status_table(list(projects.values()))
    lines = table.splitlines()
    assert lines[0].split() == [
        "PROJECT", "SESSIONS", "ACTIVE", "HIDDEN", "LAST_ACTIVITY", "COST",
    ]
    alpha = next(l for l in lines if l.startswith("alpha"))
    assert "3" in alpha and "2" in alpha and "1" in alpha
    assert _d(7_200_000 + 120_000) in alpha  # a-3 last activity date
    assert "0.75" in alpha
    beta = next(l for l in lines if l.startswith("beta"))
    assert beta.rstrip().endswith("-")  # unknown cost


def test_status_table_empty():
    assert "no projects" in render_status_table([]).lower()


def test_project_report_sections(projects):
    alpha = projects["alpha"]
    report = render_project_report(alpha, collect_milestones(alpha))
    assert report.startswith("# Project: alpha")
    assert "## Sessions" in report
    assert "| id | title | date | status | cost |" in report
    # sessions sorted by last activity desc → a-3 first
    rows = [l for l in report.splitlines() if l.startswith("| `")]
    assert rows[0].startswith("| `a-3`")
    assert "| `a-1` | alpha: initial setup |" in report
    # status + cost cells
    a3 = next(r for r in rows if "`a-3`" in r)
    assert "| active | - |" in a3
    a2 = next(r for r in rows if "`a-2`" in r)
    assert "| hidden | 0.50 |" in a2


def test_project_report_milestones_section(projects):
    alpha = projects["alpha"]
    report = render_project_report(alpha, collect_milestones(alpha))
    assert "## Milestones" in report
    assert "- [x] Alpha scaffold" in report
    assert "Done: 1/1 (100%)" in report


def test_project_report_file_milestones(projects, workdir):
    (workdir / "beta" / "milestones.json").write_text(
        json.dumps({"milestones": [{"name": "Ship it", "done": True}]}),
        encoding="utf-8",
    )
    beta = projects["beta"]
    report = render_project_report(beta, collect_milestones(beta))
    assert "- [x] Ship it" in report
    assert "- [ ] Beta MVP" in report
    assert "Done: 1/2 (50%)" in report


def test_project_report_no_milestones_omits_section(sessions_db, tmp_path):
    from devin_pm.projects import group_sessions, load_sessions

    lonely = tmp_path / "lonely"
    lonely.mkdir()
    from conftest import insert_session

    insert_session(
        sessions_db, sid="c-1", working_directory=str(lonely), title="solo"
    )
    project = next(
        p for p in group_sessions(load_sessions(sessions_db)) if p.name == "lonely"
    )
    report = render_project_report(project, [])
    assert "## Sessions" in report
    assert "## Milestones" not in report


def test_global_report(projects):
    ordered = list(projects.values())
    report = render_global_report(
        ordered, {p.name: collect_milestones(p) for p in ordered}
    )
    assert report.startswith("# devin-pm status report")
    assert "## alpha" in report
    assert "## beta" in report
    assert "### Sessions" in report
    assert "Done: 1/1 (100%)" in report
