#!/usr/bin/env python3
"""
devin-history-export.py — exporta sessões do Devin Desktop para o vault Obsidian.

Lê a DB local de sessões (%APPDATA%/devin/cli/sessions.db) — sem auth, sem API —
e gera uma nota Markdown por sessão em `Sessões/` do vault, mais um índice.

Idempotente: cada nota guarda `last_activity` no frontmatter; se a sessão não
mudou, a nota é ignorada. Seguro para correr num hook SessionEnd.

Uso:
    python scripts/devin-history-export.py            # exporta tudo (incremental)
    python scripts/devin-history-export.py --all      # força re-export
    python scripts/devin-history-export.py --dry-run  # só lista o que faria
"""

import glob
import json
import os
import re
import sqlite3
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

DB_PATH = Path.home() / "AppData/Roaming/devin/cli/sessions.db"
GUI_DB_DIR = Path.home() / "AppData/Roaming/devin/User/acp-messages"
VAULT = Path.home() / "ObsidianVault"
OUT_DIR = VAULT / "Sessões"

USER_CAP = 4000      # chars por mensagem do user
ASSISTANT_CAP = 1500  # chars por mensagem do Devin
THOUGHT_CAP = 800     # chars por pensamento do agente (GUI)
MIN_USEFUL_MSGS = 2   # sessões sem user msgs não geram nota


def slugify(text: str, maxlen: int = 40) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text[:maxlen].strip("-") or "sessao"


def clip(text: str, cap: int) -> str:
    text = text.strip()
    if len(text) > cap:
        return text[:cap] + f"\n\n*… ({len(text) - cap} chars truncados)*"
    return text


def exported_mtime(path: Path) -> int | None:
    """Lê `last_activity` do frontmatter de uma nota existente."""
    if not path.exists():
        return None
    try:
        head = path.read_text(encoding="utf-8")[:800]
        m = re.search(r"^last_activity:\s*(\d+)", head, re.MULTILINE)
        return int(m.group(1)) if m else -1
    except OSError:
        return -1


def export_session(sess, nodes) -> str:
    """Renderiza uma sessão como nota Markdown."""
    sid = sess["id"]
    title = (sess["title"] or "Sem título").strip()
    wd = sess["working_directory"] or ""
    projeto = Path(wd).name if wd else "?"
    created = datetime.fromtimestamp(sess["created_at"]).strftime("%Y-%m-%d %H:%M")

    counts = {"user": 0, "assistant": 0, "tool": 0, "system": 0}
    parts = []
    last_block = None
    for cm in nodes:
        try:
            d = json.loads(cm)
        except json.JSONDecodeError:
            continue
        role = d.get("role", "?")
        counts[role] = counts.get(role, 0) + 1
        content = (d.get("content") or "").strip()
        if not content:
            continue
        if role not in ("user", "assistant"):
            continue
        if content == last_block:
            continue  # dedup: sessões de wake repetem o mesmo prompt
        last_block = content
        label = "🧑 User" if role == "user" else "🤖 Devin"
        cap = USER_CAP if role == "user" else ASSISTANT_CAP
        parts.append(f"#### {label}\n\n{clip(content, cap)}")

    return f"""---
session_id: {sid}
projeto: {projeto}
inicio: {created}
last_activity: {sess['last_activity_at']}
msgs_user: {counts['user']}
msgs_devin: {counts['assistant']}
msgs_tool: {counts['tool']}
tags: [sessão, devin, histórico]
---

# {title}

> Sessão `{sid}` · projeto **{projeto}** · iniciada {created}
> {counts['user']} mensagens tuas · {counts['assistant']} respostas · {counts['tool']} tool calls

`{wd}`

---

## Conversa

{"".join(p + chr(10)*2 for p in parts) if parts else "_Sem mensagens user/assistant — só tool calls._"}
---

[[MOC - Sessões]]
"""


def _gui_meta(con) -> dict:
    """meta.info da DB GUI → {title, cwd}."""
    try:
        info = json.loads(con.execute(
            "SELECT value FROM meta WHERE key='info'").fetchone()[0])
    except Exception:
        return {}
    out = {"title": info.get("title") or ""}
    for opt in info.get("configOptions", []):
        if opt.get("id") in ("workspace_directories", "workspace-dirs") or \
                "Workspace" in (opt.get("name") or ""):
            cv = opt.get("currentValue")
            if isinstance(cv, list) and cv:
                out["cwd"] = cv[0]
            elif isinstance(cv, str):
                out["cwd"] = cv
    return out


def _gui_blocks(con) -> tuple:
    """(parts, counts) — reconstrói mensagens a partir dos chunks ACP.

    agent_message/agent_thought chegam em chunks (às vezes 1 char) com o
    mesmo streamingMessageId em _meta — agrega-se por esse id.
    """
    parts, counts = [], {"assistant": 0, "thought": 0, "tool": 0}
    streams: dict[str, list] = {}
    order: list[str] = []
    for kind, payload in con.execute(
            "SELECT kind, payload FROM messages ORDER BY CAST(position AS INT)"):
        try:
            d = json.loads(payload)
        except json.JSONDecodeError:
            continue
        if kind in ("agent_message", "agent_thought"):
            for c in d.get("content", []):
                txt = (c.get("content") or {}).get("text") or ""
                sid = (c.get("_meta") or {}).get("cognition.ai/streamingMessageId") \
                    or f"{kind}-{d.get('id','?')}"
                if sid not in streams:
                    streams[sid] = [kind, []]
                    order.append(sid)
                streams[sid][1].append(txt)
        elif kind == "tool_call":
            content = d.get("content") or {}
            title = content.get("title") or content.get("kind") or "tool"
            streams[f"tc-{d.get('id', len(order))}"] = ["tool", [f"`{title}`"]]
            order.append(f"tc-{d.get('id', len(order))}")
    last_block = None
    for sid in order:
        kind, chunks = streams[sid]
        text = "".join(chunks).strip()
        if not text or text == last_block:
            continue
        last_block = text
        if kind == "tool":
            counts["tool"] += 1
            parts.append(f"#### 🔧 {text}")
        elif kind == "agent_thought":
            counts["thought"] += 1
            parts.append(f"#### 💭 pensamento\n\n{clip(text, THOUGHT_CAP)}")
        else:
            counts["assistant"] += 1
            parts.append(f"#### 🤖 Devin\n\n{clip(text, ASSISTANT_CAP)}")
    return parts, counts


def export_gui_session(db_path: Path) -> str | None:
    """Renderiza uma sessão GUI (acp-messages/*.db) como nota Markdown."""
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    meta = _gui_meta(con)
    parts, counts = _gui_blocks(con)
    con.close()
    if counts["assistant"] + counts["tool"] == 0:
        return None
    sid = db_path.stem
    title = (meta.get("title") or "Sessão GUI").strip()
    wd = meta.get("cwd") or ""
    projeto = Path(wd).name if wd else "GUI"
    mtime = int(os.path.getmtime(db_path))
    created = datetime.fromtimestamp(os.path.getctime(db_path)).strftime("%Y-%m-%d %H:%M")
    return f"""---
session_id: {sid}
origem: gui-acp-messages
projeto: {projeto}
inicio: {created}
last_activity: {mtime}
msgs_devin: {counts['assistant']}
pensamentos: {counts['thought']}
msgs_tool: {counts['tool']}
tags: [sessão, devin, histórico, gui]
---

# {title}

> Sessão GUI `{sid}` · iniciada {created}
> {counts['assistant']} respostas · {counts['thought']} pensamentos · {counts['tool']} tool calls
> ⚠️ prompts do user não são gravados nesta DB — só o lado do agente.

`{wd}`

---

## Conversa (lado do agente)

{"".join(p + chr(10)*2 for p in parts)}
---

[[MOC - Sessões]]
"""


def export_gui(dry: bool, force: bool, index: list) -> tuple:
    """Passagem pelas DBs GUI. Devolve (written, skipped)."""
    written = skipped = 0
    for path in sorted(glob.glob(str(GUI_DB_DIR / "*.db"))):
        p = Path(path)
        try:
            size = os.path.getsize(p)
            if size < 4096:
                skipped += 1
                continue
            mtime = int(os.path.getmtime(p))
            date = datetime.fromtimestamp(
                os.path.getctime(p)).strftime("%Y-%m-%d")
            fname = f"{date}_gui-{p.stem[:8]}.md"
            fpath = OUT_DIR / fname
            if not force and exported_mtime(fpath) == mtime:
                skipped += 1
                continue
            body = export_gui_session(p)
            if body is None:
                skipped += 1
                continue
            if dry:
                print("exportaria (GUI):", fname)
            else:
                fpath.write_text(body, encoding="utf-8")
            written += 1
            title = re.search(r"^# (.+)$", body, re.MULTILINE).group(1)
            index.append((date, fname, title, "GUI"))
        except (OSError, sqlite3.Error):
            skipped += 1
    return written, skipped


def main() -> int:
    force = "--all" in sys.argv
    dry = "--dry-run" in sys.argv

    if not DB_PATH.exists():
        print(f"DB não encontrada: {DB_PATH}", file=sys.stderr)
        return 1

    db = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    sessions = db.execute(
        "SELECT id, title, working_directory, created_at, last_activity_at "
        "FROM sessions WHERE hidden = 0 ORDER BY created_at"
    ).fetchall()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    written, skipped, index = 0, 0, []

    for s in sessions:
        msgs = db.execute(
            "SELECT chat_message FROM message_nodes WHERE session_id=? ORDER BY node_id",
            (s["id"],),
        ).fetchall()

        roles = [json.loads(m[0]).get("role") for m in msgs if m[0].startswith("{")]
        if roles.count("user") == 0 or len(msgs) < MIN_USEFUL_MSGS:
            skipped += 1
            continue

        date = datetime.fromtimestamp(s["created_at"]).strftime("%Y-%m-%d")
        fname = f"{date}_{s['id']}.md"  # nome atómico: data + id (título vai no corpo)
        fpath = OUT_DIR / fname

        if not force and exported_mtime(fpath) == s["last_activity_at"]:
            skipped += 1
        else:
            if dry:
                print("exportaria:", fname)
            else:
                fpath.write_text(export_session(s, [m[0] for m in msgs]), encoding="utf-8")
            written += 1

        projeto = Path(s["working_directory"]).name if s["working_directory"] else "?"
        index.append((date, fname, s["title"] or "Sem título", projeto))

    # Passagem GUI — sessões do Kanban/Desktop vivem em acp-messages/*.db
    gui_written, gui_skipped = export_gui(dry, force, index)
    written += gui_written
    skipped += gui_skipped

    # MOC — índice agrupado por projeto
    moc_dir = VAULT / "MOCs"
    moc_dir.mkdir(parents=True, exist_ok=True)
    by_proj: dict[str, list] = {}
    for date, fname, title, proj in index:
        by_proj.setdefault(proj, []).append((date, fname, title))

    lines = ["---\ntags: [moc, sessões, índice]\n---\n",
             "# MOC - Sessões\n",
             f"Histórico exportado de `sessions.db` — {len(index)} sessões.\n"]
    for proj in sorted(by_proj):
        lines.append(f"\n## {proj}\n")
        for date, fname, title in sorted(by_proj[proj]):
            lines.append(f"- [[{fname[:-3]}|{date} — {title[:70]}]]")
    (moc_dir / "MOC - Sessões.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # README da pasta aponta para o MOC
    (OUT_DIR / "README.md").write_text(
        "---\ntags: [sessões, meta]\n---\n\n# Sessões\n\n"
        "Transcripts exportados de `sessions.db` (hook SessionEnd).\n"
        "Índice: [[MOC - Sessões]]\n",
        encoding="utf-8",
    )

    print(f"exportadas: {written} · ignoradas (sem mudanças/vazias): {skipped} · índice: {len(index)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
