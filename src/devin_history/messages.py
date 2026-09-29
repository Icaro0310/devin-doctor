"""Tolerant decoding of ``message_nodes.chat_message`` payloads.

SCHEMA.md marks the inner format as *unstable*: the shapes seen so far are
``{"role", "content"}`` (real store) and ``{"role", "text"}`` (fixtures).
Content may also be a list of typed blocks. We normalize the two roles
spellings (``assistant``/``agent``) and degrade gracefully on anything else.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Iterable

_ROLE_ALIASES = {
    "user": "user",
    "assistant": "assistant",
    "agent": "assistant",
    "tool": "tool",
    "system": "system",
}


@dataclass(frozen=True)
class ChatMessage:
    role: str  # normalized: user / assistant / tool / system / <raw>
    text: str
    thinking: bool
    raw: dict[str, Any]


def _block_text(block: Any) -> str:
    if isinstance(block, str):
        return block
    if isinstance(block, dict):
        inner = block.get("content")
        if isinstance(inner, dict):
            inner = inner.get("text")
        if isinstance(inner, str):
            return inner
        text = block.get("text")
        if isinstance(text, str):
            return text
    return ""


def _extract_text(d: dict[str, Any]) -> str:
    for key in ("content", "text"):
        value = d.get(key)
        if isinstance(value, str):
            return value
        if isinstance(value, list):
            parts = [_block_text(b) for b in value]
            return "\n".join(p for p in parts if p)
    return ""


def parse_chat_message(raw: str) -> ChatMessage | None:
    """Parse one ``chat_message`` blob; ``None`` when it is not a dict JSON."""
    try:
        d = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(d, dict):
        return None
    role = d.get("role")
    role_s = role if isinstance(role, str) and role else "unknown"
    return ChatMessage(
        role=_ROLE_ALIASES.get(role_s.lower(), role_s.lower()),
        text=_extract_text(d),
        thinking=bool(d.get("thinking")),
        raw=d,
    )


def parse_nodes(nodes: Iterable[Any]) -> list[ChatMessage]:
    """Decode a sequence of ``MessageNode`` (or raw ``chat_message`` str)."""
    out = []
    for n in nodes:
        raw = n.chat_message if hasattr(n, "chat_message") else n
        msg = parse_chat_message(raw)
        if msg is not None:
            out.append(msg)
    return out


def first_user_text(messages: Iterable[ChatMessage]) -> str:
    """First non-empty user message, whitespace-collapsed."""
    for m in messages:
        if m.role == "user" and m.text.strip():
            return re.sub(r"\s+", " ", m.text.strip())
    return ""
