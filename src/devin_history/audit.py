"""Full-store audit of ``sessions.db``: per-session stats, inferred status,
task classification and anomaly detection.

Status is *inferred* — the schema has no final-state column (SCHEMA.md):
``hidden`` → archived, no nodes → empty, last node = user → interrupted,
0 tool calls + ≤1 user msg → abandoned, ≥5 failed calls → with failures,
1–4 → with warnings, otherwise completed.
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from devin_history.format import project_name
from devin_history.messages import first_user_text, parse_chat_message
from devin_history.times import duration_minutes

LONG_RUNNING_MINUTES = 480.0
MANY_FAILURES = 5

SECRET_PAT = re.compile(
    r"(sk-[A-Za-z0-9_-]{8,}|ghp_[A-Za-z0-9]{8,}|gho_[A-Za-z0-9]{8,}|"
    r"xox[baprs]-[A-Za-z0-9-]{8,}|api[_-]?key\s*[:=]\s*\S+|"
    r"token\s*[:=]\s*\S+|password\s*[:=]\s*\S+|"
    r"\b[A-Za-z0-9]{20,}-[A-Za-z0-9_-]{10,}\b)",
    re.I,
)

TASK_RULES = [
    ("Bugfix", r"\b(fix|bug|erro|error|corrig|quebrad|falha|broken|crash|hotfix|regress)\b"),
    ("Refactor", r"\b(refactor|refator|cleanup|limpa|reorganiz|rename|dead code)\b"),
    ("Tests", r"\b(test|teste|pytest|coverage|cobertura|e2e|spec)\b"),
    ("Docs", r"\b(doc|readme|documenta|codemap|diagram)\b"),
    ("Migration", r"\b(migrat|upgrade|migrar)\b"),
    ("Setup / infra", r"\b(setup|install|instal|config|deploy|infra|hook|mcp\b|schedul|watchdog|startup|tunnel|túnel|vm\b|gateway|notifica|pipeline)\b"),
    ("Investigation / debugging", r"\b(investig|debug|audit|analis|analyse|porque|porquê|why|explor|understand|list|lista|review|revis|verif|check|diagnost|mapeia|inventár)\b"),
    ("Feature / implementation", r"\b(add|implement|creat|cria|faz|build|desenvolv|feat|novo|nova|gera|export|relat|automat|adiciona|melhora)\b"),
]


def redact(text: str) -> str:
    return SECRET_PAT.sub("[REDACTED]", text)


def classify_task(title: str, prompt: str) -> str:
    haystack = f"{title} {prompt}".lower()
    for name, pat in TASK_RULES:
        if re.search(pat, haystack):
            return name
    return "Other"


@dataclass(frozen=True)
class Anomaly:
    kind: str  # "empty" | "orphan" | "long-running"
    session_id: str
    detail: str


@dataclass(frozen=True)
class SessionAudit:
    id: str
    title: str
    project: str
    working_directory: str
    backend: str
    model: str
    agent_mode: str
    created_at: int
    last_activity_at: int
    duration_min: float
    hidden: bool
    user_msgs: int
    assistant_msgs: int
    tool_msgs: int
    system_msgs: int
    thinking: int
    tool_calls: int
    failed_calls: int
    tool_kinds: dict[str, int]
    files_touched: int
    files_list: list[str]
    context_tokens_max: int
    prompt_excerpt: str
    task_type: str
    status: str
    fail_samples: list[str]


@dataclass
class AuditReport:
    schema_version: int
    rows: list[SessionAudit] = field(default_factory=list)
    anomalies: list[Anomaly] = field(default_factory=list)


def _tool_stats(store) -> dict[str, dict]:
    stats: dict[str, dict] = defaultdict(lambda: {
        "calls": 0, "failed": 0, "kinds": Counter(), "files": set(),
        "fail_samples": []})
    for r in store.tool_call_state():
        st = stats[r.session_id]
        st["calls"] += 1
        call = None
        if r.tool_call_json:
            try:
                call = json.loads(r.tool_call_json)
                if isinstance(call, dict):
                    st["kinds"][call.get("kind") or "?"] += 1
                    for loc in call.get("locations") or []:
                        if isinstance(loc, dict) and loc.get("path"):
                            st["files"].add(loc["path"])
            except json.JSONDecodeError:
                pass
        status = None
        if r.tool_call_update_json:
            try:
                upd = json.loads(r.tool_call_update_json)
                status = upd.get("status") if isinstance(upd, dict) else None
                if status == "failed" and len(st["fail_samples"]) < 3:
                    txt = ""
                    for c in (upd.get("content") or []):
                        if not isinstance(c, dict):
                            continue
                        cc = c.get("content") or {}
                        if isinstance(cc, dict) and cc.get("text"):
                            txt = str(cc["text"])[:160]
                            break
                    title = call.get("title", "?") if isinstance(call, dict) else "?"
                    st["fail_samples"].append(f"{title}: {redact(txt)}")
            except json.JSONDecodeError:
                pass
        if status == "failed":
            st["failed"] += 1
    return stats


def _node_stats(store) -> dict[str, dict]:
    stats: dict[str, dict] = defaultdict(lambda: {
        "roles": Counter(), "thinking": 0, "max_tokens": 0,
        "texts": [], "last_role": None})
    for n in store.message_nodes():
        ns = stats[n.session_id]
        msg = parse_chat_message(n.chat_message)
        role = msg.role if msg is not None else "<unparsed>"
        ns["roles"][role] += 1
        ns["last_role"] = role
        if msg is not None:
            ns["texts"].append(msg)
            if msg.thinking:
                ns["thinking"] += 1
        if n.metadata:
            try:
                meta = json.loads(n.metadata) or {}
                ntp = meta.get("num_tokens_preceding")
                if ntp and ntp > ns["max_tokens"]:
                    ns["max_tokens"] = int(ntp)
            except (json.JSONDecodeError, TypeError, ValueError):
                pass
    return stats


def _status(hidden, n_nodes, last_role, user_msgs, tool_calls, failed) -> str:
    if hidden:
        return "hidden/archived"
    if n_nodes == 0:
        return "empty"
    if last_role == "user":
        return "interrupted (no final reply)"
    if tool_calls == 0 and user_msgs <= 1:
        return "abandoned (no actions)"
    if failed >= MANY_FAILURES:
        return "completed with failures"
    if failed > 0:
        return "completed with warnings"
    return "completed (inferred)"


def audit_store(store, *, long_running_minutes: float = LONG_RUNNING_MINUTES) -> AuditReport:
    """Audit every session in an open read-only ``SessionsStore``."""
    tool_stats = _tool_stats(store)
    node_stats = _node_stats(store)
    sessions = sorted(store.sessions(), key=lambda s: s.created_at)
    session_ids = {s.id for s in sessions}

    report = AuditReport(schema_version=store.schema_info["schema_version"])

    referenced: dict[str, set[str]] = defaultdict(set)
    for n in store.message_nodes():
        referenced[n.session_id].add("message_nodes")
    for tc in store.tool_call_state():
        referenced[tc.session_id].add("tool_call_state")
    for p in store.prompt_history():
        referenced[p.session_id].add("prompt_history")
    for sid in sorted(set(referenced) - session_ids):
        report.anomalies.append(Anomaly(
            "orphan", sid,
            f"rows in {', '.join(sorted(referenced[sid]))} reference a session "
            "that is not in the sessions table",
        ))

    for s in sessions:
        ns = node_stats.get(s.id, {"roles": Counter(), "thinking": 0,
                                   "max_tokens": 0, "texts": [], "last_role": None})
        ts = tool_stats.get(s.id, {"calls": 0, "failed": 0, "kinds": Counter(),
                                   "files": set(), "fail_samples": []})
        roles = ns["roles"]
        user_msgs = roles.get("user", 0)
        n_nodes = sum(roles.values())
        prompt = redact(first_user_text(ns["texts"])[:220])
        duration = round(duration_minutes(s.created_at, s.last_activity_at), 1)
        status = _status(s.hidden, n_nodes, ns["last_role"], user_msgs,
                         ts["calls"], ts["failed"])

        report.rows.append(SessionAudit(
            id=s.id,
            title=(s.title or "Untitled").strip(),
            project=project_name(s.working_directory),
            working_directory=s.working_directory,
            backend=s.backend_type,
            model=s.model or "N/D",
            agent_mode=s.agent_mode or "N/D",
            created_at=s.created_at,
            last_activity_at=s.last_activity_at,
            duration_min=duration,
            hidden=s.hidden,
            user_msgs=user_msgs,
            assistant_msgs=roles.get("assistant", 0),
            tool_msgs=roles.get("tool", 0),
            system_msgs=roles.get("system", 0),
            thinking=ns["thinking"],
            tool_calls=ts["calls"],
            failed_calls=ts["failed"],
            tool_kinds=dict(ts["kinds"]),
            files_touched=len(ts["files"]),
            files_list=sorted(ts["files"]),
            context_tokens_max=ns["max_tokens"],
            prompt_excerpt=prompt,
            task_type=classify_task(s.title or "", prompt),
            status=status,
            fail_samples=ts["fail_samples"],
        ))

        if n_nodes == 0:
            report.anomalies.append(Anomaly(
                "empty", s.id, "session row with no message nodes"))
        if duration >= long_running_minutes:
            report.anomalies.append(Anomaly(
                "long-running", s.id,
                f"{duration:.0f} min active (>= {long_running_minutes:.0f} min)"))

    return report
