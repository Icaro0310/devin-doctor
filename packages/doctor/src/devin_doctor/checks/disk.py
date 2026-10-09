"""Check 5 — disk: total data-dir footprint, largest DB files, and
``acp-messages`` accumulation (count/bytes/mtime span)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from devin_doctor.model import Context, Finding, Status
from devin_doctor.paths import human_size, locate_stores

CHECK_ID = "disk"

_TOP_N = 3


def _day(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")


def _total_finding(ctx: Context, total: int, n_files: int) -> Finding:
    message = f"data dir total: {human_size(total)} across {n_files} files"
    if total > ctx.total_warn_bytes:
        return Finding(
            CHECK_ID,
            Status.WARN,
            f"{message} (>{human_size(ctx.total_warn_bytes)})",
            fix="Largest offenders are usually acp-messages DBs and Cache/"
            "blob_storage — archive or prune old session data.",
        )
    return Finding(CHECK_ID, Status.PASS, message)


def _largest_finding(ctx: Context, files: list[Path]) -> Finding:
    dbs = [p for p in files if p.suffix in (".db", ".vscdb")]
    top = sorted(dbs, key=lambda p: p.stat().st_size, reverse=True)[:_TOP_N]
    if not top:
        return Finding(
            CHECK_ID, Status.PASS, "no .db/.vscdb stores found under data dir"
        )
    listing = ", ".join(
        f"{p.name} ({human_size(p.stat().st_size)})" for p in top
    )
    oversized = [p for p in top if p.stat().st_size > ctx.store_warn_bytes]
    if oversized:
        return Finding(
            CHECK_ID,
            Status.WARN,
            f"largest stores: {listing} — over "
            f"{human_size(ctx.store_warn_bytes)}",
            fix="Consider exporting old sessions (devin-history) and vacuuming "
            "— an offline VACUUM is planned for --fix (M2).",
        )
    return Finding(CHECK_ID, Status.PASS, f"largest stores: {listing}")


def _acp_finding(ctx: Context) -> Finding:
    stores = locate_stores(ctx.data_dir)
    if not stores.acp_dbs:
        return Finding(
            CHECK_ID, Status.PASS, "acp-messages: no accumulation (0 db files)"
        )
    total = sum(p.stat().st_size for p in stores.acp_dbs)
    mtimes = sorted(p.stat().st_mtime for p in stores.acp_dbs)
    span = f"{_day(mtimes[0])} .. {_day(mtimes[-1])}"
    message = (
        f"acp-messages accumulation: {len(stores.acp_dbs)} db(s), "
        f"{human_size(total)}, span {span}"
    )
    if total > ctx.acp_warn_bytes:
        return Finding(
            CHECK_ID,
            Status.WARN,
            f"{message} (>{human_size(ctx.acp_warn_bytes)})",
            fix="Per-session acp DBs accumulate forever — archive sessions you "
            "no longer need.",
        )
    return Finding(CHECK_ID, Status.PASS, message)


def run(ctx: Context) -> list[Finding]:
    if not ctx.data_dir.is_dir():
        return [
            Finding(
                CHECK_ID,
                Status.FAIL,
                f"Devin data dir not found: {ctx.data_dir}",
                fix="Pass --data-dir pointing at the Devin data directory.",
            )
        ]
    files = [p for p in ctx.data_dir.rglob("*") if p.is_file()]
    total = sum(p.stat().st_size for p in files)
    return [
        _total_finding(ctx, total, len(files)),
        _largest_finding(ctx, files),
        _acp_finding(ctx),
    ]
