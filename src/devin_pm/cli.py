"""``devin-pm`` — thin CLI wrapper; all logic lives in the library.

Subcommands (all read-only against ``sessions.db``):

- ``status``      per-project rollup table (``--json`` for machines)
- ``report``      markdown report for ``--project`` or every project
- ``milestones``  milestone list + done % for ``--project``
- ``registry``    emit machine-readable ``registry.json``

Exit codes: 0 ok · 1 read/parse error · 2 missing db / unknown project.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Sequence

from devin_internals.parsers import Session, SessionsStore
from devin_internals.schema import SchemaError

from devin_pm.milestones import (
    MilestonesError,
    collect_milestones,
    done_fraction,
)
from devin_pm.projects import (
    Project,
    default_sessions_db,
    find_project,
    group_sessions,
)
from devin_pm.registry import build_registry, write_registry
from devin_pm.report import (
    ms_to_iso,
    render_global_report,
    render_project_report,
    render_status_table,
)


class _CliError(RuntimeError):
    """Expected CLI failure; ``exit_code`` goes to the process."""

    def __init__(self, message: str, exit_code: int = 1) -> None:
        self.exit_code = exit_code
        super().__init__(message)


def _print_json(payload: object) -> None:
    print(json.dumps(payload, indent=2))


def _resolve_db(args: argparse.Namespace) -> Path:
    path = (
        Path(args.sessions_db).expanduser()
        if args.sessions_db
        else default_sessions_db()
    )
    if not path.is_file():
        raise _CliError(
            f"{path}: no sessions.db there — pass --sessions-db or set "
            "DEVIN_PM_SESSIONS_DB",
            exit_code=2,
        )
    return path


def _load(db_path: Path) -> tuple[list[Session], int]:
    with SessionsStore(db_path) as store:
        return store.sessions(), store.schema_info["schema_version"]


def _projects(db_path: Path) -> tuple[list[Project], int]:
    sessions, version = _load(db_path)
    return group_sessions(sessions), version


def _require_project(projects: list[Project], name: str) -> Project:
    project = find_project(projects, name)
    if project is None:
        known = ", ".join(p.name for p in projects) or "(none)"
        raise _CliError(
            f"unknown project '{name}' — known projects: {known}",
            exit_code=2,
        )
    return project


def _project_json(project: Project) -> dict:
    return {
        "name": project.name,
        "working_directory": project.working_directory,
        "sessions": project.session_count,
        "status": project.status_counts,
        "last_activity": ms_to_iso(project.last_activity_at),
        "cost": project.cost,
    }


# ---------------------------------------------------------------------------
# subcommands
# ---------------------------------------------------------------------------


def cmd_status(args: argparse.Namespace) -> int:
    projects, _ = _projects(_resolve_db(args))
    if args.json:
        _print_json([_project_json(p) for p in projects])
    else:
        print(render_status_table(projects))
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    projects, _ = _projects(_resolve_db(args))
    if args.project:
        project = _require_project(projects, args.project)
        text = render_project_report(project, collect_milestones(project))
    else:
        text = render_global_report(
            projects, {p.name: collect_milestones(p) for p in projects}
        )
    if args.out:
        out = Path(args.out)
        out.write_text(text, encoding="utf-8")
        print(f"wrote {out}")
    else:
        print(text, end="")
    return 0


def _milestones_json(project: Project) -> dict:
    ms = collect_milestones(project)
    done, total, pct = done_fraction(ms)
    return {
        "project": project.name,
        "milestones": [
            {
                "name": m.name,
                "done": m.done,
                "session_id": m.session_id,
                "source": m.source,
            }
            for m in ms
        ],
        "done": done,
        "total": total,
        "percent": round(pct, 1),
    }


def cmd_milestones(args: argparse.Namespace) -> int:
    projects, _ = _projects(_resolve_db(args))
    project = _require_project(projects, args.project)
    if args.json:
        _print_json(_milestones_json(project))
        return 0
    ms = collect_milestones(project)
    done, total, pct = done_fraction(ms)
    print(f"Project: {project.name}")
    if not ms:
        print("(no milestones — tag a session title `milestone: <name>` or "
              "add milestones.json to the project root)")
        return 0
    for m in ms:
        where = f" (session {m.session_id})" if m.session_id else ""
        print(f"- [{'x' if m.done else ' '}] {m.name}{where}")
    print(f"Done: {done}/{total} ({pct:.0f}%)")
    return 0


def cmd_registry(args: argparse.Namespace) -> int:
    db_path = _resolve_db(args)
    projects, version = _projects(db_path)
    registry = build_registry(
        projects,
        milestones={p.name: collect_milestones(p) for p in projects},
        sessions_db=db_path,
        schema_version=version,
    )
    if args.out:
        print(f"wrote {write_registry(registry, args.out)}")
    else:
        _print_json(registry)
    return 0


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="devin-pm",
        description=(
            "Project manager over Devin sessions — groups sessions.db per "
            "working directory into projects, reports, milestones and a "
            "machine-readable registry. Read-only, always."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def with_db(p: argparse.ArgumentParser) -> argparse.ArgumentParser:
        p.add_argument(
            "--sessions-db",
            metavar="PATH",
            help="path to sessions.db (default: auto-detect "
            "%%APPDATA%%/devin/cli/sessions.db, or DEVIN_PM_SESSIONS_DB)",
        )
        return p

    p = with_db(sub.add_parser("status", help="per-project rollup table"))
    p.add_argument("--json", action="store_true", help="JSON output")
    p.set_defaults(func=cmd_status)

    p = with_db(sub.add_parser("report", help="markdown status report"))
    p.add_argument(
        "--project",
        metavar="NAME",
        help="project name (working-directory basename); omit for a "
        "global report over all projects",
    )
    p.add_argument("--out", metavar="FILE", help="write markdown to FILE")
    p.set_defaults(func=cmd_report)

    p = with_db(
        sub.add_parser("milestones", help="list a project's milestones")
    )
    p.add_argument("--project", required=True, metavar="NAME")
    p.add_argument("--json", action="store_true", help="JSON output")
    p.set_defaults(func=cmd_milestones)

    p = with_db(
        sub.add_parser("registry", help="emit registry.json")
    )
    p.add_argument(
        "--out",
        metavar="FILE",
        help="write registry.json to FILE (default: stdout)",
    )
    p.set_defaults(func=cmd_registry)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except _CliError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exc.exit_code
    except MilestonesError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except SchemaError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except (sqlite3.Error, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
