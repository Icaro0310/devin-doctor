"""Thin CLI wrapper — all logic lives in the library modules."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from devin_internals import SchemaError

from devin_search import __version__
from devin_search.fmt import (
    hits_table,
    hits_to_dicts,
    stats_line,
    stats_to_dict,
)
from devin_search.index import build_index
from devin_search.paths import (
    default_acp_dir,
    default_index_path,
    default_sessions_db,
)
from devin_search.query import parse_since, search


def _resolve_index(arg: str | None) -> Path:
    return Path(arg).expanduser() if arg else default_index_path()


def _cmd_index(args: argparse.Namespace) -> int:
    sessions_db = (
        Path(args.sessions_db).expanduser()
        if args.sessions_db
        else default_sessions_db()
    )
    acp_dir = (
        Path(args.acp_dir).expanduser()
        if args.acp_dir
        else default_acp_dir()
    )
    if sessions_db is None and acp_dir is None:
        print(
            "devin-search: no Devin stores found in the default locations; "
            "pass --sessions-db and/or --acp-dir",
            file=sys.stderr,
        )
        return 2
    if sessions_db is not None and not sessions_db.exists():
        print(
            f"devin-search: {sessions_db}: no such file", file=sys.stderr
        )
        return 2
    try:
        stats = build_index(
            _resolve_index(args.index),
            sessions_db=sessions_db,
            acp_dir=acp_dir,
            rebuild=args.rebuild,
        )
    except SchemaError as exc:
        print(f"devin-search: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(stats_to_dict(stats), ensure_ascii=False, indent=2))
    else:
        print(stats_line(stats))
    return 0


def _cmd_query(args: argparse.Namespace) -> int:
    try:
        since = parse_since(args.since) if args.since else None
    except ValueError:
        print(
            f"devin-search: --since {args.since!r} is not a date "
            "(YYYY-MM-DD) or epoch ms",
            file=sys.stderr,
        )
        return 2
    try:
        hits = search(
            _resolve_index(args.index),
            args.term,
            role=args.role,
            project=args.project,
            since=since,
            limit=args.limit,
        )
    except FileNotFoundError as exc:
        print(f"devin-search: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(
            json.dumps(
                {"term": args.term, "hits": hits_to_dicts(hits)},
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(hits_table(hits))
    return 0 if hits else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="devin-search",
        description="Full-text search across all Devin sessions "
        "(sessions.db + acp-messages → local FTS5 index).",
    )
    p.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    sub = p.add_subparsers(dest="command", required=True)

    ix = sub.add_parser(
        "index", help="build/update the local search index (incremental)"
    )
    ix.add_argument(
        "--sessions-db",
        help="path to Devin's sessions.db (default: auto-detect)",
    )
    ix.add_argument(
        "--acp-dir",
        help="path to Devin's User/acp-messages dir (default: auto-detect)",
    )
    ix.add_argument("--index", help="index file path (default: app dir)")
    ix.add_argument(
        "--rebuild",
        action="store_true",
        help="drop and rebuild the index from scratch",
    )
    ix.add_argument(
        "--json", action="store_true", help="machine-readable JSON output"
    )
    ix.set_defaults(func=_cmd_index)

    q = sub.add_parser("query", help="search the index")
    q.add_argument("term", help="free-text search (tokens ANDed)")
    q.add_argument("--role", help="filter: user/assistant/tool/system/shell")
    q.add_argument(
        "--project", help="substring filter on the session working directory"
    )
    q.add_argument(
        "--since", help="only hits at/after this date (YYYY-MM-DD or epoch ms)"
    )
    q.add_argument("--limit", type=int, default=20)
    q.add_argument("--index", help="index file path (default: app dir)")
    q.add_argument(
        "--json", action="store_true", help="machine-readable JSON output"
    )
    q.set_defaults(func=_cmd_query)
    return p


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
