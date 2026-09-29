"""Thin CLI wrapper — all logic lives in the library modules.

- ``devin-doctor check [--data-dir P] [--cwd P] [--stale-days N] [--json]``
- ``devin-doctor report [--data-dir P] [--cwd P] [--stale-days N] [--md|--json]``

Exit code: 0 when no FAIL findings, 1 when any check FAILs.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from devin_doctor import doctor
from devin_doctor.model import Context
from devin_doctor.paths import default_data_dir


def _add_common(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Devin data dir (default: platform location — "
        "%%APPDATA%%/devin on Windows, ~/.config/devin elsewhere)",
    )
    p.add_argument(
        "--cwd",
        type=Path,
        default=Path.cwd(),
        help="project dir whose .devin/ config to check (default: cwd)",
    )
    p.add_argument(
        "--stale-days",
        type=int,
        default=30,
        metavar="N",
        help="flag sessions inactive for more than N days (default: 30)",
    )
    p.add_argument("--json", action="store_true", help="emit JSON")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="devin-doctor",
        description="Diagnose a Devin Desktop installation: stores, schema "
        "versions, data health, config sanity, disk usage. Read-only, always.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="run all checks and print findings")
    _add_common(check)

    report = sub.add_parser(
        "report", help="same findings, formatted for pasting into issues"
    )
    _add_common(report)
    report.add_argument(
        "--md", action="store_true", help="emit markdown (for GitHub issues)"
    )

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    ctx = Context(
        data_dir=args.data_dir or default_data_dir(),
        cwd=args.cwd,
        stale_days=args.stale_days,
    )
    report = doctor.run_all(ctx)
    if args.json:
        print(doctor.render_json(report, ctx))
    elif args.command == "report" and args.md:
        print(doctor.render_markdown(report, ctx))
    else:
        print(doctor.render_text(report))
    return doctor.exit_code(report)


if __name__ == "__main__":
    raise SystemExit(main())
