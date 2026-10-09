"""Extract GUI-side nodes/edges from Devin's ``state.vscdb`` (GR-1).

``state.vscdb`` is the Electron store (``ItemTable`` key/value) under
``User/globalStorage/`` of the Devin config dir. The only keys this reads
are the observed ``windsurfSpace.*`` family:

- ``windsurfSpace.sessionWorkspace/<backend>/<slug>`` — JSON
  ``{workspaceId, label, folders[], lastUpdated}`` binding a GUI session
  (identified by a generated slug like ``canyon-newspaper``) to a workspace.
- ``windsurfSpace.resourceToSpace`` — ``{space_id: [editor URIs]}``; URIs
  look like ``vscode-cascade-editor:///cascade-acp/<backend>/<slug>``.
- ``windsurfSpace.metadata`` — ``{space_id: {lastAccessed: ms}}``.

Coverage is deliberately best-effort: unknown or malformed keys are skipped,
never fatal, and the store is opened read-only (``mode=ro`` + ``query_only``).

Produces ``gui_session`` nodes (key = slug) and ``gui_workspace`` edges
``gui_session → project``. When a space points at a slug, its ``space_id``
and ``lastAccessed`` enrich the session node's attrs.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from devin_graph.extract import Edge, Extraction, Node

SESSION_WS_PREFIX = "windsurfSpace.sessionWorkspace/"
RESOURCE_TO_SPACE = "windsurfSpace.resourceToSpace"
SPACE_METADATA = "windsurfSpace.metadata"
_EDITOR_URI_PREFIX = "vscode-cascade-editor:///cascade-acp/"


def extract_vscdb(path: str | Path) -> Extraction:
    """``state.vscdb`` → gui_session/gui_workspace nodes and edges."""
    p = Path(path).expanduser()
    con = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
    try:
        con.execute("PRAGMA query_only = ON")
        rows = dict(
            con.execute("SELECT key, value FROM ItemTable").fetchall())
    except sqlite3.Error as exc:
        raise ValueError(f"{p}: not a readable state.vscdb ({exc})") from exc
    finally:
        con.close()

    ex = Extraction()
    last_accessed = _space_last_accessed(rows)
    space_of = _space_of_session(rows)

    for key, raw in rows.items():
        if not key.startswith(SESSION_WS_PREFIX):
            continue
        backend, sep, slug = key[len(SESSION_WS_PREFIX):].rpartition("/")
        if not sep or not slug:
            continue
        data = _json_dict(raw)
        workspace = data.get("workspaceId")
        folders = data.get("folders") or []
        attrs: dict[str, Any] = {
            "backend": backend,
            "label": data.get("label"),
            "workspace": workspace,
            "folders": folders,
            "lastUpdated": data.get("lastUpdated"),
        }
        space = space_of.get(slug)
        if space:
            attrs["space_id"] = space
            if space in last_accessed:
                attrs["lastAccessed"] = last_accessed[space]
        ex.nodes.append(Node("gui_session", slug, attrs))
        if workspace:
            ex.nodes.append(
                Node("project", workspace, {"name": Path(workspace).name}))
            ex.edges.append(
                Edge("gui_workspace", ("gui_session", slug),
                     ("project", workspace)))
    return ex


def _json_dict(raw: Any) -> dict:
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", "replace")
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _space_last_accessed(rows: dict) -> dict[str, int]:
    meta = _json_dict(rows.get(SPACE_METADATA))
    out = {}
    for space_id, m in meta.items():
        if isinstance(m, dict) and isinstance(m.get("lastAccessed"), int):
            out[space_id] = m["lastAccessed"]
    return out


def _space_of_session(rows: dict) -> dict[str, str]:
    """session slug → space_id, via resourceToSpace editor URIs."""
    out: dict[str, str] = {}
    rts = _json_dict(rows.get(RESOURCE_TO_SPACE))
    for space_id, uris in rts.items():
        if not isinstance(uris, list):
            continue
        for uri in uris:
            if isinstance(uri, str) and uri.startswith(_EDITOR_URI_PREFIX):
                slug = uri[len(_EDITOR_URI_PREFIX):].rstrip("/").rsplit(
                    "/", 1)[-1]
                if slug:
                    out.setdefault(slug, space_id)
    return out
