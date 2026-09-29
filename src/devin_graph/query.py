"""Canned queries over a built ``graph.db``.

Matching is forgiving: exact key first, then case-insensitive, then suffix
(so ``src/app.py`` finds ``/repo/alpha/src/app.py``). All functions return
plain JSON-ready dicts.
"""

from __future__ import annotations

from itertools import combinations

from devin_graph.extract import normalize_path


def _session_dict(gs, node) -> dict:
    project = None
    for e in gs.out_edges(node.id):
        if e.kind == "runs_in":
            project = e.dst.split(":", 1)[1]
    return {
        "id": node.key,
        "title": node.attrs.get("title"),
        "project": project,
        "last_activity_at": node.attrs.get("last_activity_at"),
    }


def _match_file_keys(gs, query: str) -> list[str]:
    q = normalize_path(query) or query.strip()
    keys = [n.key for n in gs.nodes("file")]
    exact = [k for k in keys if k == q]
    if exact:
        return sorted(exact)
    ci = [k for k in keys if k.casefold() == q.casefold()]
    if ci:
        return sorted(ci)
    return sorted(k for k in keys if k.endswith("/" + q) or k == q)


def _match_project_keys(gs, query: str) -> list[str]:
    q = normalize_path(query) or query.strip()
    nodes = gs.nodes("project")
    exact = [n for n in nodes if n.key == q]
    if exact:
        return sorted(n.key for n in exact)
    named = [n for n in nodes if n.attrs.get("name") == query.strip()]
    ci = [n for n in nodes
          if n.key.casefold() == q.casefold()
          or (n.attrs.get("name") or "").casefold() == query.strip().casefold()]
    found = {n.key for n in named + ci}
    if found:
        return sorted(found)
    return sorted(n.key for n in nodes
                  if n.key.endswith("/" + q) or n.key == q)


def _match_tool_keys(gs, query: str) -> list[str]:
    q = query.strip()
    return sorted(n.key for n in gs.nodes("tool")
                  if n.key == q or n.key.casefold() == q.casefold())


def _sessions_of_project(gs, project_key: str) -> list[str]:
    return sorted(
        e.src.split(":", 1)[1]
        for e in gs.in_edges(f"project:{project_key}")
        if e.kind == "runs_in"
    )


def sessions_for_file(gs, path: str) -> dict:
    """Which sessions touched ``path``, via which tool calls."""
    file_keys = _match_file_keys(gs, path)
    tool_calls = []
    session_ids: set[str] = set()
    for fk in file_keys:
        for e in gs.in_edges(f"file:{fk}"):
            if e.kind != "file_touched":
                continue
            tool_calls.append({
                "id": e.src.split(":", 1)[1],
                "session_id": e.owner,
                "file": fk,
            })
            if e.owner:
                session_ids.add(e.owner)
    tool_calls.sort(key=lambda t: t["id"])
    sessions = [
        _session_dict(gs, gs.node(f"session:{sid}"))
        for sid in sorted(session_ids)
        if gs.node(f"session:{sid}") is not None
    ]
    return {"query": path, "files": file_keys, "sessions": sessions,
            "tool_calls": tool_calls}


def sessions_for_tool(gs, name: str) -> dict:
    """Which sessions/projects used tool ``name``."""
    session_ids: set[str] = set()
    projects: set[str] = set()
    for key in _match_tool_keys(gs, name):
        for e in gs.in_edges(f"tool:{key}"):
            if e.kind == "tool_used" and e.owner:
                session_ids.add(e.owner)
    sessions = [
        _session_dict(gs, gs.node(f"session:{sid}"))
        for sid in sorted(session_ids)
        if gs.node(f"session:{sid}") is not None
    ]
    for s in sessions:
        if s["project"]:
            projects.add(s["project"])
    return {"tool": name, "sessions": sessions,
            "projects": sorted(projects)}


def tools_for_project(gs, query: str) -> dict:
    """Tools used by sessions running in project ``query``."""
    project_keys = _match_project_keys(gs, query)
    session_ids = sorted({
        sid for pk in project_keys for sid in _sessions_of_project(gs, pk)
    })
    tools: set[str] = set()
    for sid in session_ids:
        for e in gs.out_edges(f"session:{sid}"):
            if e.kind == "tool_used":
                tools.add(e.dst.split(":", 1)[1])
    sessions = [
        _session_dict(gs, gs.node(f"session:{sid}"))
        for sid in session_ids
        if gs.node(f"session:{sid}") is not None
    ]
    return {"query": query, "projects": project_keys, "tools": sorted(tools),
            "sessions": sessions}


def project_detail(gs, query: str) -> dict:
    """One project: its sessions, the tools they used, the files they touched."""
    keys = _match_project_keys(gs, query)
    if not keys:
        return {"project": None, "sessions": [], "tools": [], "files": []}
    project_key = keys[0]
    base = tools_for_project(gs, project_key)
    session_ids = {s["id"] for s in base["sessions"]}
    files = sorted({
        e.dst.split(":", 1)[1]
        for e in gs.edges("file_touched")
        if e.owner in session_ids
    })
    return {"project": project_key, "sessions": base["sessions"],
            "tools": base["tools"], "files": files}


def projects_graph(gs) -> dict:
    """Project-to-project adjacency for visualization (D3-style).

    Two projects link when they share a tool (both used it) or a file (both
    touched it); ``weight`` = number of shared entities.
    """
    projects = gs.nodes("project")
    tools_by_project: dict[str, set[str]] = {p.key: set() for p in projects}
    files_by_project: dict[str, set[str]] = {p.key: set() for p in projects}

    for e in gs.edges("tool_used"):
        proj = _project_of_session(gs, e.src.split(":", 1)[1])
        if proj in tools_by_project:
            tools_by_project[proj].add(e.dst.split(":", 1)[1])
    for e in gs.edges("file_touched"):
        proj = _project_of_session(gs, e.owner)
        if proj in files_by_project:
            files_by_project[proj].add(e.dst.split(":", 1)[1])

    nodes = [{
        "id": p.key,
        "name": p.attrs.get("name"),
        "sessions": _sessions_of_project(gs, p.key),
    } for p in projects]

    links = []
    for a, b in combinations(sorted(tools_by_project), 2):
        shared_tools = sorted(tools_by_project[a] & tools_by_project[b])
        shared_files = sorted(files_by_project[a] & files_by_project[b])
        if shared_tools or shared_files:
            links.append({
                "source": a, "target": b,
                "weight": len(shared_tools) + len(shared_files),
                "shared_tools": shared_tools,
                "shared_files": shared_files,
            })
    return {"nodes": nodes, "links": links}


def _project_of_session(gs, session_id: str | None) -> str | None:
    if session_id is None:
        return None
    for e in gs.out_edges(f"session:{session_id}"):
        if e.kind == "runs_in":
            return e.dst.split(":", 1)[1]
    return None
