"""Markdown status reports and the plain-text rollup table."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, Mapping

from devin_pm.milestones import Milestone, done_fraction
from devin_pm.projects import Project, extract_cost


def ms_to_date(ts_ms: int | None) -> str:
    """Epoch ms → ``YYYY-MM-DD`` (UTC); ``-`` when missing."""
    if ts_ms is None:
        return "-"
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")


def ms_to_iso(ts_ms: int | None) -> str:
    """Epoch ms → ISO-8601 ``YYYY-MM-DDTHH:MM:SSZ`` (UTC); ``-`` when missing."""
    if ts_ms is None:
        return "-"
    return (
        datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def fmt_cost(cost: float | None) -> str:
    """``0.75`` → ``"0.75"``; ``None`` (unknown) → ``"—"``."""
    return f"{cost:.2f}" if cost is not None else "—"


def _fmt_table(headers: list[str], rows: list[list[str]]) -> str:
    widths = [max([len(h), *(len(r[i]) for r in rows)]) for i, h in enumerate(headers)]
    line = "  ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
    sep = "  ".join("-" * widths[i] for i in range(len(headers)))
    body = ["  ".join(r[i].ljust(widths[i]) for i in range(len(headers))) for r in rows]
    return "\n".join([line, sep, *body])


def render_status_table(projects: Iterable[Project]) -> str:
    """Per-project rollup for ``devin-pm status``."""
    projects = list(projects)
    if not projects:
        return "no projects"
    rows = [
        [
            p.name,
            str(p.session_count),
            str(p.status_counts.get("active", 0)),
            str(p.status_counts.get("hidden", 0)),
            ms_to_date(p.last_activity_at),
            fmt_cost(p.cost),
        ]
        for p in projects
    ]
    return _fmt_table(
        ["PROJECT", "SESSIONS", "ACTIVE", "HIDDEN", "LAST_ACTIVITY", "COST"], rows
    )


def _sessions_table(project: Project) -> list[str]:
    lines = [
        "| id | title | date | status | cost |",
        "|---|---|---|---|---|",
    ]
    for s in project.sessions:
        title = (s.title or "—").replace("|", "\\|")
        lines.append(
            f"| `{s.id}` | {title} | {ms_to_date(s.last_activity_at)} "
            f"| {s.status} | {fmt_cost(extract_cost(s.cogs_json))} |"
        )
    return lines


def _milestone_lines(milestones: Iterable[Milestone]) -> list[str]:
    ms = list(milestones)
    if not ms:
        return []
    lines = [""]
    lines += [f"- [{'x' if m.done else ' '}] {m.name}" for m in ms]
    done, total, pct = done_fraction(ms)
    lines += ["", f"Done: {done}/{total} ({pct:.0f}%)"]
    return lines


def _summary_line(project: Project) -> str:
    counts = project.status_counts
    mix = ", ".join(f"{n} {k}" for k, n in sorted(counts.items()))
    return (
        f"_{project.session_count} sessions · last activity "
        f"{ms_to_date(project.last_activity_at)} · {mix} · cost "
        f"{fmt_cost(project.cost)}_"
    )


def render_project_report(project: Project, milestones: Iterable[Milestone]) -> str:
    """``# Project: <name>`` report with sessions + milestones."""
    lines = [
        f"# Project: {project.name}",
        "",
        _summary_line(project),
        "",
        "## Sessions",
        "",
        *_sessions_table(project),
    ]
    tail = _milestone_lines(milestones)
    if tail:
        lines += ["", "## Milestones", *tail]
    return "\n".join(lines) + "\n"


def render_global_report(
    projects: Iterable[Project], milestones: Mapping[str, Iterable[Milestone]]
) -> str:
    """``# devin-pm status report`` — every project, one section each."""
    projects = list(projects)
    lines = [
        "# devin-pm status report",
        "",
        f"_{len(projects)} projects · "
        f"{sum(p.session_count for p in projects)} sessions · generated "
        f"{datetime.now(tz=timezone.utc).strftime('%Y-%m-%d')}_",
    ]
    for project in projects:
        lines += [
            "",
            f"## {project.name}",
            "",
            _summary_line(project),
            "",
            "### Sessions",
            "",
            *_sessions_table(project),
        ]
        tail = _milestone_lines(milestones.get(project.name, ()))
        if tail:
            lines += ["", "### Milestones", *tail]
    return "\n".join(lines) + "\n"
