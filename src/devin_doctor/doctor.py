"""Runner + renderers for devin-doctor reports.

``run_all`` executes every registered check (a crashing check degrades to a
FAIL finding instead of aborting the run). Renderers produce the three
output shapes: text lines, the ``--json`` contract, and a markdown report.
"""

from __future__ import annotations

import json
import platform
from datetime import datetime, timezone

import devin_doctor
from devin_doctor.checks import CHECKS
from devin_doctor.model import Context, Finding, Report, Status, platform_name


def run_all(ctx: Context) -> Report:
    report = Report()
    for check in CHECKS:
        try:
            report.findings += check.run(ctx)
        except Exception as exc:  # noqa: BLE001 — a doctor must not die
            report.findings.append(
                Finding(
                    check.CHECK_ID,
                    Status.FAIL,
                    f"check crashed: {exc!r}",
                    fix="Report a bug at "
                    "https://github.com/Icaro0310/devin-doctor/issues",
                )
            )
    return report


def exit_code(report: Report) -> int:
    return 1 if report.overall is Status.FAIL else 0


def render_text(report: Report) -> str:
    lines: list[str] = []
    check_status = report.check_status()
    for check_id, status in check_status.items():
        lines.append(f"{check_id} — {status}")
        for f in report.findings:
            if f.check != check_id:
                continue
            lines.append(f"  {f.status.value:<4}  {f.message}")
            if f.fix and f.status is not Status.PASS:
                lines.append(f"        fix: {f.fix}")
    counts = report.counts()
    lines.append("")
    lines.append(
        f"overall: {report.overall.value} "
        f"({counts['pass']} PASS, {counts['warn']} WARN, {counts['fail']} FAIL)"
    )
    return "\n".join(lines)


def render_json(report: Report, ctx: Context) -> str:
    payload = {
        "tool": "devin-doctor",
        "version": devin_doctor.__version__,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "platform": platform_name(),
        "data_dir": str(ctx.data_dir),
        "cwd": str(ctx.cwd),
        "overall": report.overall.value,
        "summary": report.counts(),
        "checks": report.check_status(),
        "findings": [f.as_dict() for f in report.findings],
    }
    return json.dumps(payload, indent=2)


def render_markdown(report: Report, ctx: Context) -> str:
    counts = report.counts()
    lines = [
        "# devin-doctor report",
        "",
        f"- generated: {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        f"- devin-doctor: {devin_doctor.__version__}",
        f"- platform: {platform_name()} ({platform.python_version()})",
        f"- data dir: `{ctx.data_dir}`",
        f"- project dir: `{ctx.cwd}`",
        f"- **overall: {report.overall.value}** "
        f"({counts['pass']} PASS / {counts['warn']} WARN / {counts['fail']} FAIL)",
        "",
        "| check | status | finding |",
        "|---|---|---|",
    ]
    for f in report.findings:
        msg = f.message.replace("|", "\\|")
        lines.append(f"| {f.check} | {f.status.value} | {msg} |")
    fixes = [f for f in report.findings if f.fix and f.status is not Status.PASS]
    if fixes:
        lines += ["", "## Suggested fixes", ""]
        lines += [f"- **{f.check}**: {f.fix}" for f in fixes]
    return "\n".join(lines)
