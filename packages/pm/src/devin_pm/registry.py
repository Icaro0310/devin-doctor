"""``registry.json`` — machine-consumable project registry.

Same spirit as the ecosystem hub registry (devin-powerups/registry.json):
a versioned JSON document that other tools can consume without parsing
markdown or touching ``sessions.db`` themselves.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from devin_pm.milestones import Milestone, done_fraction
from devin_pm.projects import Project
from devin_pm.report import ms_to_iso

REGISTRY_VERSION = 1
REGISTRY_SCHEMA_URL = (
    "https://github.com/Icaro0310/devin-pm/registry.schema.json"
)


def _project_entry(
    project: Project, milestones: Iterable[Milestone] | None
) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "name": project.name,
        "working_directory": project.working_directory,
        "sessions": project.session_count,
        "gui_sessions": project.gui_session_count,
        "session_ids": project.session_ids,
        "last_activity": ms_to_iso(project.last_activity_at),
        "status": project.status_counts,
        "cost": project.cost,
    }
    if milestones is not None:
        done, total, _ = done_fraction(milestones)
        entry["milestones"] = {
            "total": total,
            "done": done,
            "pending": total - done,
        }
    return entry


def build_registry(
    projects: Iterable[Project],
    *,
    milestones: Mapping[str, Iterable[Milestone]] | None = None,
    sessions_db: str | Path | None = None,
    state_vscdb: str | Path | None = None,
    schema_version: int | None = None,
    generated: str | None = None,
) -> dict[str, Any]:
    """Assemble the registry document.

    ``cost`` is ``None`` where the source data has no recognizable cost
    fields (``cogs_json`` is unstable) — ``None`` means unknown, not zero.
    """
    projects = list(projects)
    if generated is None:
        generated = (
            datetime.now(tz=timezone.utc).isoformat(timespec="seconds")
            .replace("+00:00", "Z")
        )

    source: dict[str, Any] = {}
    if sessions_db is not None:
        source["sessions_db"] = str(sessions_db)
    if state_vscdb is not None:
        source["state_vscdb"] = str(state_vscdb)
    if schema_version is not None:
        source["schema_version"] = schema_version

    known_costs = [p.cost for p in projects if p.cost is not None]
    return {
        "$schema": REGISTRY_SCHEMA_URL,
        "version": REGISTRY_VERSION,
        "generated": generated,
        "source": source,
        "projects": [
            _project_entry(p, milestones.get(p.name) if milestones else None)
            for p in projects
        ],
        "totals": {
            "projects": len(projects),
            "sessions": sum(p.session_count for p in projects),
            "cost": sum(known_costs) if known_costs else None,
        },
    }


def write_registry(registry: Mapping[str, Any], out_path: str | Path) -> Path:
    """Write the registry as pretty JSON; returns the path."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(registry, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return out_path
