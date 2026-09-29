"""Extract graph nodes/edges from a ``sessions.db`` (via ``SessionsStore``).

Node kinds: ``session``, ``project`` (the session's ``working_directory``),
``file`` (a path touched by a tool call), ``tool`` (tool name) and
``tool_call`` (one row of ``tool_call_state`` — the ground truth of what the
agent actually invoked).

Edge kinds:

- ``runs_in``       session → project
- ``made_call``     session → tool_call
- ``call_used``     tool_call → tool
- ``tool_used``     session → tool
- ``file_touched``  tool_call → file

``tool_call_json`` is marked *unstable* in SCHEMA.md, so payload decoding is
deliberately defensive: file paths are collected from any recognised path-ish
key anywhere in the payload, plus path-looking tokens inside command strings.
Relative paths resolve against the session's ``working_directory``.
"""

from __future__ import annotations

import json
import posixpath
import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Iterator

NODE_KINDS = ("session", "project", "file", "tool", "tool_call")
EDGE_KINDS = ("runs_in", "made_call", "call_used", "tool_used", "file_touched")

# Payload keys whose string value(s) are file/dir paths.
_PATH_KEYS = {
    "path", "paths", "file", "files", "filename", "file_path", "filepath",
    "fileName".lower(), "abs_path", "absolute_path", "target_file",
}

# Payload keys whose string value is a shell-like command to mine for paths.
_COMMAND_KEYS = {"command", "cmd", "script", "shell_command", "input"}

# Tool-name candidate keys, in priority order, checked at top level and one
# level deep (rawInput/raw_input/input carry the real tool input in ACP).
_TOOL_NAME_KEYS = ("name", "tool_name", "tool", "kind", "type", "title")
_NESTED_KEYS = ("rawInput", "raw_input", "input", "args")

# Path-looking token inside a command string: either contains a separator or
# is a bare filename with a recognisable code/docs extension.
_PATH_TOKEN_RE = re.compile(
    r"(?:[A-Za-z]:[\\/]|\.{1,2}/|/)?[\w@+~.-]+(?:[\\/][\w@+~.-]+)+"
    r"|[\w@+~.-]+\.(?:py|pyi|js|jsx|ts|tsx|mjs|cjs|json|toml|ya?ml|md|txt|rst"
    r"|rs|go|c|h|cc|cpp|hpp|java|kt|rb|sh|bash|bat|ps1|sql|html?|css|scss|xml"
    r"|csv|cfg|ini|env|lock|ipynb)\b"
)
_TOKEN_STRIP = "\"'`.,;:()[]{}"


@dataclass(frozen=True)
class Node:
    kind: str
    key: str
    attrs: dict = field(default_factory=dict, compare=False)


@dataclass(frozen=True)
class Edge:
    kind: str
    src: tuple[str, str]  # (node kind, node key)
    dst: tuple[str, str]
    attrs: dict = field(default_factory=dict, compare=False)


@dataclass
class Extraction:
    """Nodes/edges produced from one or more sessions (deduplicated)."""

    nodes: list[Node] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)

    def merged(self) -> "Extraction":
        seen_n: dict[tuple[str, str], Node] = {}
        seen_e: set[tuple] = set()
        out = Extraction()
        for n in self.nodes:
            seen_n.setdefault((n.kind, n.key), n)
        out.nodes = list(seen_n.values())
        for e in self.edges:
            k = (e.kind, e.src, e.dst)
            if k not in seen_e:
                seen_e.add(k)
                out.edges.append(e)
        return out


def normalize_path(raw: Any) -> str | None:
    """Canonical path string: ``/`` separators, no ``.`` segments, no quotes.

    Returns ``None`` for empty/non-string input.
    """
    if not isinstance(raw, str):
        return None
    p = raw.strip().strip("\"'").strip()
    if not p:
        return None
    p = p.replace("\\", "/")
    is_abs = p.startswith("/") or re.match(r"^[A-Za-z]:/", p) is not None
    p = posixpath.normpath(p)
    if p == ".":
        return None
    if not is_abs and p.startswith("/"):
        p = p.lstrip("/")
    return p or None


def _is_absolute(p: str) -> bool:
    return p.startswith("/") or re.match(r"^[A-Za-z]:/", p) is not None


def _resolve(path: str, cwd: str | None) -> str:
    """Anchor relative paths to the session's working directory."""
    if _is_absolute(path) or not cwd:
        return path
    base = normalize_path(cwd) or ""
    return posixpath.normpath(f"{base}/{path}") if base else path


def parse_payload(text: str | None) -> dict | None:
    """Decode a ``tool_call_*_json`` payload; ``None`` on anything unusable."""
    if not text:
        return None
    try:
        data = json.loads(text)
    except (TypeError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _walk_strings(node: Any) -> Iterator[str]:
    if isinstance(node, dict):
        for v in node.values():
            yield from _walk_strings(v)
    elif isinstance(node, list):
        for v in node:
            yield from _walk_strings(v)
    elif isinstance(node, str):
        yield node


def _iter_keyed(node: Any) -> Iterator[tuple[str, Any]]:
    """Yield ``(lowercased_key, value)`` for every dict entry, recursively."""
    if isinstance(node, dict):
        for k, v in node.items():
            yield str(k).lower(), v
            yield from _iter_keyed(v)
    elif isinstance(node, list):
        for v in node:
            yield from _iter_keyed(v)


def extract_tool_name(payload: dict) -> str | None:
    """Best-effort tool name from an unstable payload shape."""
    for key in _TOOL_NAME_KEYS:
        v = payload.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    for nest in _NESTED_KEYS:
        sub = payload.get(nest)
        if isinstance(sub, dict):
            for key in _TOOL_NAME_KEYS:
                v = sub.get(key)
                if isinstance(v, str) and v.strip():
                    return v.strip()
    return None


def _paths_from_command(text: str) -> set[str]:
    found = set()
    for m in _PATH_TOKEN_RE.finditer(text):
        tok = m.group(0).strip(_TOKEN_STRIP)
        preceded_by_scheme = re.search(
            r"[A-Za-z][\w+.-]*:/+$", text[: m.start()]) is not None
        if (not tok or "://" in tok or tok.startswith("//")
                or preceded_by_scheme):
            continue
        if tok.lstrip("./").startswith("-"):  # a flag, not a path
            continue
        norm = normalize_path(tok)
        if norm:
            found.add(norm)
    return found


def extract_paths(payload: dict) -> set[str]:
    """All file/dir paths referenced by a tool-call payload (normalized)."""
    found: set[str] = set()
    for key, value in _iter_keyed(payload):
        if key in _PATH_KEYS:
            if isinstance(value, str):
                norm = normalize_path(value)
                if norm and "://" not in norm:
                    found.add(norm)
            elif isinstance(value, (list, dict)):
                for s in _walk_strings(value):
                    norm = normalize_path(s)
                    if norm and "://" not in norm:
                        found.add(norm)
        elif key in _COMMAND_KEYS and isinstance(value, str):
            found |= _paths_from_command(value)
    return found


def extract_session(session, tool_calls: Iterable) -> Extraction:
    """One session → nodes + edges.

    ``session`` is a ``devin_internals.parsers.Session``; ``tool_calls`` are
    its ``ToolCallState`` rows.
    """
    ex = Extraction()
    sid = session.id
    cwd = normalize_path(session.working_directory)

    ex.nodes.append(Node("session", sid, {
        "title": session.title,
        "model": session.model,
        "created_at": session.created_at,
        "last_activity_at": session.last_activity_at,
        "hidden": session.hidden,
    }))
    if cwd:
        ex.nodes.append(Node("project", cwd, {"name": posixpath.basename(cwd)}))
        ex.edges.append(Edge("runs_in", ("session", sid), ("project", cwd)))

    for tc in tool_calls:
        call_key = f"{sid}:{tc.tool_call_id}"
        ex.nodes.append(Node("tool_call", call_key, {
            "tool_call_id": tc.tool_call_id,
            "session_id": sid,
        }))
        ex.edges.append(
            Edge("made_call", ("session", sid), ("tool_call", call_key)))

        # Merge update then call payloads (call wins); tolerate NULL/junk.
        payload = {}
        for raw in (tc.tool_call_update_json, tc.tool_call_json):
            data = parse_payload(raw)
            if data:
                payload = {**payload, **data}

        tool = extract_tool_name(payload) if payload else None
        if tool:
            ex.nodes.append(Node("tool", tool, {}))
            ex.edges.append(
                Edge("call_used", ("tool_call", call_key), ("tool", tool)))
            ex.edges.append(
                Edge("tool_used", ("session", sid), ("tool", tool)))

        for path in sorted(extract_paths(payload)):
            resolved = _resolve(path, cwd)
            ex.nodes.append(
                Node("file", resolved, {"name": posixpath.basename(resolved)}))
            ex.edges.append(Edge(
                "file_touched", ("tool_call", call_key), ("file", resolved)))

    return ex


def extract_all(store) -> Extraction:
    """Every session in ``store`` → merged, deduplicated graph."""
    combined = Extraction()
    for session in store.sessions():
        part = extract_session(session, store.tool_call_state(session.id))
        combined.nodes.extend(part.nodes)
        combined.edges.extend(part.edges)
    return combined.merged()
