#!/usr/bin/env python3
"""
audit_sessions.py — auditoria lifetime das sessões do Devin Desktop.

Fontes:
  - %APPDATA%/devin/cli/sessions.db          (sessões CLI: sessions, message_nodes, tool_call_state)
  - %APPDATA%/devin/User/acp-messages/*.db   (sessões GUI)
  - %APPDATA%/devin/cli/session_locks/*.lock (locks → órfãos = sessões removidas)
  - %APPDATA%/devin/cli/logs/*.log.gz        (logs de arranque)
  - %APPDATA%/devin/cli/summaries/*.md       (resumos gerados)
  - <ws>/.devin/memory/session-*.jsonl       (prompts logados por hooks)

Saída: sessions_report.md + sessions_summary.csv no workspace.
"""

import csv
import glob
import json
import os
import re
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

HOME = Path.home()
DB_PATH = HOME / "AppData/Roaming/devin/cli/sessions.db"
GUI_DB_DIR = HOME / "AppData/Roaming/devin/User/acp-messages"
LOCKS_DIR = HOME / "AppData/Roaming/devin/cli/session_locks"
LOGS_DIR = HOME / "AppData/Roaming/devin/cli/logs"
SUMMARIES_DIR = HOME / "AppData/Roaming/devin/cli/summaries"
WS = Path(os.environ.get("AUDIT_WORKSPACE", Path(__file__).resolve().parent.parent))
MEM_DIR = WS / ".devin" / "memory"

SECRET_PAT = re.compile(
    r"(sk-[A-Za-z0-9_-]{8,}|ghp_[A-Za-z0-9]{8,}|gho_[A-Za-z0-9]{8,}|"
    r"xox[baprs]-[A-Za-z0-9-]{8,}|api[_-]?key\s*[:=]\s*\S+|"
    r"token\s*[:=]\s*\S+|password\s*[:=]\s*\S+|"
    r"\b[A-Za-z0-9]{20,}-[A-Za-z0-9_-]{10,}\b)", re.IGNORECASE)


def redact(t: str) -> str:
    return SECRET_PAT.sub("[REDACTED]", t)


def ts(v) -> str:
    return datetime.fromtimestamp(v).strftime("%Y-%m-%d %H:%M:%S") if v else ""


def classify_task(title: str, prompt: str) -> str:
    t = f"{title} {prompt}".lower()
    rules = [
        ("Bugfix", r"\b(fix|bug|erro|error|corrig|quebrad|falha|broken|crash|hotfix|regress)\b"),
        ("Refactor", r"\b(refactor|refator|cleanup|limpa|reorganiz|rename|dead code)\b"),
        ("Testes", r"\b(test|teste|pytest|coverage|cobertura|e2e|spec)\b"),
        ("Documentação", r"\b(doc|readme|documenta|codemap|diagram)\b"),
        ("Migração", r"\b(migrat|upgrade|migrar)\b"),
        ("Setup / infra", r"\b(setup|install|instal|config|deploy|infra|hook|mcp\b|schedul|watchdog|startup|tunnel|túnel|vm\b|gateway|slack|notifica|pipeline)\b"),
        ("Investigação / debugging", r"\b(investig|debug|audit|auditoria|analis|analise|porque|porquê|why|explor|entende|understand|list|lista|review|revis|verific|check|diagnost|mapeia|inventár)\b"),
        ("Feature / implementação", r"\b(add|implement|creat|cria|faz|build|desenvolv|feat|novo|nova|gera|export|relat|automat|adiciona|melhora|implementa)\b"),
    ]
    for name, pat in rules:
        if re.search(pat, t):
            return name
    return "Outros"


def first_user_prompt(nodes) -> str:
    for cm in nodes:
        try:
            d = json.loads(cm)
        except json.JSONDecodeError:
            continue
        if d.get("role") == "user" and (d.get("content") or "").strip():
            return re.sub(r"\s+", " ", d["content"].strip())
    return ""


def session_rows():
    con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row

    tool_stats = defaultdict(lambda: {
        "calls": 0, "failed": 0, "kinds": Counter(), "files": set(),
        "fail_samples": []})
    for r in con.execute(
            "SELECT session_id, tool_call_json, tool_call_update_json FROM tool_call_state"):
        st = tool_stats[r["session_id"]]
        st["calls"] += 1
        if r["tool_call_json"]:
            try:
                d = json.loads(r["tool_call_json"])
                st["kinds"][d.get("kind") or "?"] += 1
                for loc in d.get("locations") or []:
                    p = loc.get("path")
                    if p:
                        st["files"].add(p)
            except json.JSONDecodeError:
                pass
        status = None
        if r["tool_call_update_json"]:
            try:
                u = json.loads(r["tool_call_update_json"])
                status = u.get("status")
                if status == "failed" and len(st["fail_samples"]) < 3:
                    txt = ""
                    for c in u.get("content") or []:
                        cc = c.get("content") or {}
                        if cc.get("text"):
                            txt = cc["text"][:160]
                            break
                    st["fail_samples"].append(
                        (json.loads(r["tool_call_json"]).get("title", "?")
                         if r["tool_call_json"] else "?") + ": " + redact(txt))
            except json.JSONDecodeError:
                pass
        if status == "failed":
            st["failed"] += 1

    node_stats = defaultdict(lambda: {
        "roles": Counter(), "thinking": 0, "max_tokens": 0, "nodes": [],
        "last_role": None})
    for r in con.execute(
            "SELECT session_id, chat_message, metadata FROM message_nodes "
            "ORDER BY session_id, node_id"):
        ns = node_stats[r["session_id"]]
        ns["nodes"].append(r["chat_message"])
        try:
            d = json.loads(r["chat_message"])
            role = d.get("role", "?")
            ns["roles"][role] += 1
            ns["last_role"] = role
            if d.get("thinking"):
                ns["thinking"] += 1
        except json.JSONDecodeError:
            ns["roles"]["<unparsed>"] += 1
        if r["metadata"]:
            try:
                m = json.loads(r["metadata"]) or {}
                ntp = m.get("num_tokens_preceding")
                if ntp and ntp > ns["max_tokens"]:
                    ns["max_tokens"] = ntp
            except json.JSONDecodeError:
                pass

    rows = []
    for s in con.execute(
            "SELECT id,title,working_directory,backend_type,model,agent_mode,"
            "created_at,last_activity_at,hidden FROM sessions ORDER BY created_at"):
        sid = s["id"]
        ns = node_stats.get(sid, {"roles": Counter(), "thinking": 0,
                                  "max_tokens": 0, "nodes": [], "last_role": None})
        tst = tool_stats.get(sid, {"calls": 0, "failed": 0, "kinds": Counter(),
                                   "files": set(), "fail_samples": []})
        prompt = first_user_prompt(ns["nodes"])
        roles = ns["roles"]
        user_msgs = roles.get("user", 0)
        asst_msgs = roles.get("assistant", 0)
        n_files = len(tst["files"])

        if s["hidden"]:
            status = "oculta/arquivada"
        elif ns["last_role"] == "user":
            status = "interrompida (sem resposta final)"
        elif tst["calls"] == 0 and user_msgs <= 1:
            status = "abandonada (sem ações)"
        elif tst["failed"] >= 5:
            status = "concluída c/ falhas"
        elif tst["failed"] > 0:
            status = "concluída c/ warnings"
        else:
            status = "concluída (inferido)"

        score = user_msgs * 3 + tst["calls"] + n_files * 2
        complexity = ("simples" if score < 10 else "média" if score < 60
                      else "alta" if score < 200 else "muito alta")

        rows.append({
            "origin": "cli",
            "id": sid,
            "title": (s["title"] or "Sem título").strip(),
            "project": Path(s["working_directory"].replace("\\\\wsl.localhost\\Ubuntu", "wsl:")).name
                       if s["working_directory"] else "?",
            "working_directory": s["working_directory"],
            "backend": s["backend_type"], "model": s["model"] or "N/D",
            "agent_mode": s["agent_mode"] or "N/D",
            "created": s["created_at"], "last_activity": s["last_activity_at"],
            "duration_min": round((s["last_activity_at"] - s["created_at"]) / 60, 1),
            "hidden": s["hidden"],
            "user_msgs": user_msgs, "assistant_msgs": asst_msgs,
            "tool_msgs": roles.get("tool", 0), "system_msgs": roles.get("system", 0),
            "thinking": ns["thinking"],
            "tool_calls": tst["calls"], "failed_calls": tst["failed"],
            "tool_kinds": dict(tst["kinds"]),
            "files_touched": n_files,
            "files_list": sorted(tst["files"]),
            "context_tokens_max": ns["max_tokens"],
            "prompt": redact(prompt[:220]),
            "task_type": classify_task(s["title"] or "", prompt),
            "status": status,
            "fail_samples": tst["fail_samples"],
        })
    con.close()
    return rows


def gui_rows():
    rows = []
    for p in sorted(glob.glob(str(GUI_DB_DIR / "*.db"))):
        if p.endswith(("-shm", "-wal")):
            continue
        path = Path(p)
        try:
            if os.path.getsize(path) < 4096:
                continue
            con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
            try:
                info = json.loads(con.execute(
                    "SELECT value FROM meta WHERE key='info'").fetchone()[0])
            except Exception:
                info = {}
            title = info.get("title") or ""
            cwd = ""
            for opt in info.get("configOptions", []):
                if opt.get("id") in ("workspace_directories", "workspace-dirs") \
                        or "Workspace" in (opt.get("name") or ""):
                    cv = opt.get("currentValue")
                    cwd = cv[0] if isinstance(cv, list) and cv else (cv or "")
            if isinstance(cwd, str) and cwd.startswith("["):
                try:
                    parsed = json.loads(cwd)
                    cwd = parsed[0] if isinstance(parsed, list) and parsed else ""
                except json.JSONDecodeError:
                    pass
            kinds = Counter()
            first_prompt = ""
            for kind, payload in con.execute(
                    "SELECT kind, payload FROM messages ORDER BY CAST(position AS INT)"):
                kinds[kind] += 1
                if not first_prompt and kind == "user_message":
                    try:
                        d = json.loads(payload)
                        txt = "".join(
                            (c.get("content") or {}).get("text") or ""
                            for c in d.get("content", []))
                        first_prompt = re.sub(r"\s+", " ", txt.strip())
                    except json.JSONDecodeError:
                        pass
            con.close()
            ctime = int(os.path.getctime(path))
            mtime = int(os.path.getmtime(path))
            n_calls = kinds.get("tool_call", 0)
            score = kinds.get("user_message", 0) * 3 + n_calls
            rows.append({
                "origin": "gui",
                "id": path.stem,
                "title": title.strip() or "Sem título",
                "project": Path(cwd).name if cwd else "GUI",
                "working_directory": cwd,
                "backend": "gui-acp", "model": "N/D", "agent_mode": "N/D",
                "created": ctime, "last_activity": mtime,
                "duration_min": round((mtime - ctime) / 60, 1),
                "hidden": 0,
                "user_msgs": kinds.get("user_message", 0),
                "assistant_msgs": kinds.get("agent_message", 0),
                "tool_msgs": 0, "system_msgs": 0,
                "thinking": kinds.get("agent_thought", 0),
                "tool_calls": n_calls, "failed_calls": 0,
                "tool_kinds": {"tool_call": n_calls} if n_calls else {},
                "files_touched": 0, "files_list": [],
                "context_tokens_max": 0,
                "prompt": redact(first_prompt[:220]),
                "task_type": classify_task(title, first_prompt),
                "status": "concluída (inferido)" if kinds.get("agent_message") else "vazia",
                "fail_samples": [],
            })
        except (OSError, sqlite3.Error):
            continue
    return rows


def main():
    cli = session_rows()
    gui = gui_rows()
    rows = cli + gui

    ids = {r["id"] for r in cli}
    locks = {Path(p).stem for p in glob.glob(str(LOCKS_DIR / "*.lock"))}
    orphan_locks = sorted(locks - ids)

    mem_sessions = {}
    for p in glob.glob(str(MEM_DIR / "session-*.jsonl")):
        slug = Path(p).stem[len("session-"):]
        try:
            mem_sessions[slug] = sum(1 for _ in open(p, encoding="utf-8"))
        except OSError:
            mem_sessions[slug] = 0

    log_files = glob.glob(str(LOGS_DIR / "*.log*"))
    log_dates = sorted(re.search(r"devin_(\d{8})", os.path.basename(p)).group(1)
                       for p in log_files if re.search(r"devin_(\d{8})", os.path.basename(p)))
    n_summaries = len(glob.glob(str(SUMMARIES_DIR / "*.md")))

    with open(WS / "sessions_summary.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["origin", "session_id", "title", "project", "backend", "model",
                    "agent_mode", "created", "last_activity", "duration_min", "hidden",
                    "status", "task_type", "user_msgs", "assistant_msgs", "tool_calls",
                    "failed_calls", "files_touched", "context_tokens_max", "prompt_excerpt"])
        for r in rows:
            w.writerow([r["origin"], r["id"], r["title"], r["project"], r["backend"],
                        r["model"], r["agent_mode"], ts(r["created"]), ts(r["last_activity"]),
                        r["duration_min"], r["hidden"], r["status"], r["task_type"],
                        r["user_msgs"], r["assistant_msgs"], r["tool_calls"],
                        r["failed_calls"], r["files_touched"], r["context_tokens_max"],
                        r["prompt"]])

    out = WS / "audit_out.json"
    out.write_text(json.dumps({
        "rows": rows, "orphan_locks": orphan_locks,
        "mem_sessions": mem_sessions,
        "log_range": (log_dates[0], log_dates[-1], len(log_files)) if log_dates else None,
        "n_summaries": n_summaries}, ensure_ascii=False, default=str), encoding="utf-8")
    render_report(rows, orphan_locks, mem_sessions,
                  (log_dates[0], log_dates[-1], len(log_files)) if log_dates else None,
                  n_summaries)
    print(f"cli={len(cli)} gui={len(gui)} orphan_locks={len(orphan_locks)} "
          f"logs={len(log_files)} summaries={n_summaries} mem={len(mem_sessions)}")


STATUS_GROUPS = [
    ("✅ Concluídas (inferido)", lambda r: r["status"] == "concluída (inferido)"),
    ("⚠️ Concluídas com warnings (1–4 tool calls falhados)",
     lambda r: r["status"] == "concluída c/ warnings"),
    ("❌ Concluídas com muitas falhas (≥5 tool calls falhados)",
     lambda r: r["status"] == "concluída c/ falhas"),
    ("⏱️ Interrompidas (última mensagem = user, sem resposta final)",
     lambda r: r["status"].startswith("interrompida")),
    ("🚫 Ocultas / arquivadas", lambda r: r["status"].startswith("oculta")),
    ("💤 Abandonadas sem ações", lambda r: r["status"].startswith("abandonada")),
    ("🕳️ Vazias (DB GUI sem mensagens do agente)",
     lambda r: r["status"] == "vazia"),
]


def _fmt_dur(mins: float) -> str:
    if mins < 60:
        return f"{mins:.0f}m"
    return f"{mins/60:.1f}h"


def _sess_line(r) -> str:
    p = f" — _{r['prompt'][:90]}…_" if r["prompt"] else ""
    return (f"| `{r['id']}` | {ts(r['created'])[:16]} | {_fmt_dur(r['duration_min'])} "
            f"| {r['user_msgs']} | {r['tool_calls']} ({r['failed_calls']}✗) "
            f"| {r['files_touched']} | {r['title'][:60]}{p} |")


def render_report(rows, orphan_locks, mem_sessions, log_info, n_summaries):
    L = []
    A = L.append
    cli = [r for r in rows if r["origin"] == "cli"]
    gui = [r for r in rows if r["origin"] == "gui"]
    total = len(rows)
    t0 = min(r["created"] for r in rows)
    t1 = max(r["last_activity"] for r in rows)
    ok = sum(1 for r in rows if r["status"].startswith("concluída"))
    dur_active = sum(r["duration_min"] for r in rows)

    A("# RELATÓRIO TÉCNICO TOTAL — LIFETIME DE SESSIONS")
    A(f"\n_Gerado em {datetime.now().strftime('%Y-%m-%d %H:%M')} por "
      "`scripts/audit_sessions.py`_\n")

    A("## 1. Sumário Executivo\n")
    A(f"- **Total de sessions:** {total} ({len(cli)} CLI/agente · {len(gui)} GUI/ACP)")
    A(f"- **Período coberto:** {ts(t0)[:10]} → {ts(t1)[:10]} "
      f"(~{round((t1-t0)/86400)} dias)")
    A(f"- **Taxa de conclusão inferida:** {ok}/{total} "
      f"({ok*100//total}%) — _a DB não grava status explícito; inferência descrita "
      "na secção 3.1_")
    A(f"- **Duração média (criação→última atividade):** "
      f"{_fmt_dur(dur_active/total)} · mediana "
      f"{_fmt_dur(sorted(r['duration_min'] for r in rows)[total//2])}")
    A(f"- **Mensagens de user:** {sum(r['user_msgs'] for r in rows)} · "
      f"**Tool calls:** {sum(r['tool_calls'] for r in rows)} "
      f"({sum(r['failed_calls'] for r in rows)} falhados)")
    A("- **Tokens/custo:** NÃO DISPONÍVEL — a DB não grava consumo nem billing; "
      "só `num_tokens_preceding` (tamanho de contexto) existe por nó")
    A(f"- **Fontes extra:** {len(orphan_locks)} locks órfãos (sessões removidas), "
      f"{n_summaries} summaries, {len(mem_sessions)} logs de prompts em `.devin/memory/`")
    A("- **Temas dominantes:** pokeemerald-expansion (ROM hack), "
      "personal-agent-system (infra do próprio agente), PetSaas, automação "
      "Slack/Obsidian/Djævin\n")

    A("## 2. Estatísticas Agregadas\n")
    A("### Por status\n")
    A("| Status | N |")
    A("|---|---|")
    for label, pred in STATUS_GROUPS:
        n = sum(1 for r in rows if pred(r))
        A(f"| {label} | {n} |")
    A("\n### Por tipo de tarefa\n")
    A("| Tipo | CLI | GUI | Total |")
    A("|---|---|---|---|")
    tt = Counter(r["task_type"] for r in rows)
    for k, v in tt.most_common():
        A(f"| {k} | {sum(1 for r in cli if r['task_type']==k)} "
          f"| {sum(1 for r in gui if r['task_type']==k)} | {v} |")
    A("\n### Por repositório / projeto\n")
    A("| Projeto | Sessions | Tool calls |")
    A("|---|---|---|")
    for k, v in Counter(r["project"] for r in rows).most_common():
        A(f"| {k} | {v} | {sum(r['tool_calls'] for r in rows if r['project']==k)} |")
    A("\n### Por modelo (sessões CLI)\n")
    A("| Modelo | N |")
    A("|---|---|")
    for k, v in Counter(r["model"] for r in cli).most_common():
        A(f"| {k} | {v} |")
    A("\n### Ferramentas mais usadas (por `kind`)\n")
    A("| Kind | N |")
    A("|---|---|")
    kinds = Counter()
    for r in rows:
        kinds.update(r["tool_kinds"])
    for k, v in kinds.most_common():
        A(f"| {k} | {v} |")
    A("")

    A("## 3. Grupos de Sessions\n")
    A("### 3.1 Por Status\n")
    A("> A DB não tem coluna de status final — a classificação é **inferida**: "
      "`hidden`→arquivada; último nó=`user`→interrompida; 0 tool calls+≤1 msg→"
      "abandonada; ≥5 tool calls falhados→c/ falhas; 1–4→warnings; resto→concluída.\n")
    for label, pred in STATUS_GROUPS:
        sub = [r for r in rows if pred(r)]
        A(f"#### {label} — {len(sub)}\n")
        if not sub:
            A("_(nenhuma)_\n")
            continue
        A("| Session | Início | Duração | Msgs user | Tool calls | Files | Título/prompt |")
        A("|---|---|---|---|---|---|---|")
        for r in sorted(sub, key=lambda r: r["created"]):
            A(_sess_line(r))
        A("")

    A("### 3.2 Por Tipo de Tarefa\n")
    for k, _ in tt.most_common():
        sub = [r for r in rows if r["task_type"] == k]
        A(f"#### {k} — {len(sub)}\n")
        A("| Session | Origem | Início | Tool calls | Título |")
        A("|---|---|---|---|---|")
        for r in sorted(sub, key=lambda r: r["created"]):
            A(f"| `{r['id']}` | {r['origin']} | {ts(r['created'])[:16]} "
              f"| {r['tool_calls']} | {r['title'][:70]} |")
        A("")

    A("### 3.3 Por Repositório / Projeto\n")
    for k, v in Counter(r["project"] for r in rows).most_common():
        sub = [r for r in rows if r["project"] == k]
        A(f"#### {k} — {len(sub)}\n")
        wds = sorted({r["working_directory"] for r in sub})
        for wd in wds:
            A(f"- `{wd}`")
        A("")
        A("| Session | Origem | Início | Tool calls | Status | Título |")
        A("|---|---|---|---|---|---|")
        for r in sorted(sub, key=lambda r: r["created"]):
            A(f"| `{r['id']}` | {r['origin']} | {ts(r['created'])[:16]} "
              f"| {r['tool_calls']} | {r['status']} | {r['title'][:60]} |")
        A("")

    A("### 3.4 Por Usuário / Workspace\n")
    A("**Usuário único:** máquina local Windows — sem multi-tenant. "
      "Workspaces = `working_directory`:\n")
    A("| Workspace | Sessions |")
    A("|---|---|")
    for k, v in Counter(r["working_directory"] for r in rows).most_common():
        A(f"| `{k}` | {v} |")
    A("")

    A("### 3.5 Por Período\n")
    A("| Mês | Sessions | Tool calls | Msgs user |")
    A("|---|---|---|---|")
    months = Counter(ts(r["created"])[:7] for r in rows)
    for m in sorted(months):
        sub = [r for r in rows if ts(r["created"])[:7] == m]
        A(f"| {m} | {len(sub)} | {sum(r['tool_calls'] for r in sub)} "
          f"| {sum(r['user_msgs'] for r in sub)} |")
    A("")

    A("### 3.6 Por Complexidade\n")
    A("> Heurística: `score = msgs_user×3 + tool_calls + ficheiros×2` → "
      "simples <10 · média <60 · alta <200 · muito alta ≥200\n")
    for label, pred in [
        ("Simples", lambda r: r["user_msgs"]*3 + r["tool_calls"] + r["files_touched"]*2 < 10),
        ("Média", lambda r: 10 <= r["user_msgs"]*3 + r["tool_calls"] + r["files_touched"]*2 < 60),
        ("Alta", lambda r: 60 <= r["user_msgs"]*3 + r["tool_calls"] + r["files_touched"]*2 < 200),
        ("Muito alta", lambda r: r["user_msgs"]*3 + r["tool_calls"] + r["files_touched"]*2 >= 200)]:
        sub = [r for r in rows if pred(r)]
        A(f"#### {label} — {len(sub)}\n")
        if label in ("Alta", "Muito alta"):
            A("| Session | Score | Tool calls | Files | Título |")
            A("|---|---|---|---|---|")
            for r in sorted(sub, key=lambda r: -(r["tool_calls"] + r["files_touched"])):
                sc = r["user_msgs"]*3 + r["tool_calls"] + r["files_touched"]*2
                A(f"| `{r['id']}` | {sc} | {r['tool_calls']} "
                  f"| {r['files_touched']} | {r['title'][:60]} |")
            A("")
        else:
            ids = ", ".join(f"`{r['id']}`" for r in sub)
            A(ids + "\n")

    A("### 3.7 Incidentes Críticos\n")
    incidents = [r for r in rows if r["failed_calls"] >= 5]
    A(f"Sessions com ≥5 tool calls falhados: **{len(incidents)}**\n")
    for r in sorted(incidents, key=lambda r: -r["failed_calls"]):
        A(f"#### `{r['id']}` — {r['failed_calls']} falhados — {r['title'][:60]}")
        for s in r["fail_samples"]:
            A(f"- `{s[:150]}`")
        A("")

    A("## 4. Linha do Tempo\n")
    A("```")
    for m in sorted(months):
        n = months[m]
        A(f"{m} | {'█' * n} {n}")
    A("```\n")
    A("Primeira session: `" + min(rows, key=lambda r: r["created"])["id"] + "` "
      f"({ts(t0)}) · última: `" +
      max(rows, key=lambda r: r["last_activity"])["id"] + f"` ({ts(t1)})\n")

    A("## 5. Padrões e Insights\n")
    top_tools = kinds.most_common(3)
    A(f"- **Ferramenta dominante:** `{top_tools[0][0]}` ({top_tools[0][1]} calls) — "
      "o uso é massivamente shell/execute, seguido de edit e read.")
    fail_sessions = [r for r in rows if r["failed_calls"] > 0]
    A(f"- **Falhas de tool calls:** {sum(r['failed_calls'] for r in rows)} em "
      f"{len(fail_sessions)} sessions; concentradas em "
      f"{', '.join('`'+r['id']+'`' for r in sorted(fail_sessions, key=lambda r: -r['failed_calls'])[:3])}.")
    A(f"- **Workspace principal:** `personal-agent-system` "
      f"({sum(1 for r in rows if 'personal-agent-system' in r['working_directory'])} "
      "sessions) — meta-trabalho no próprio agente (hooks, MCPs, Djævin, Slack bridge).")
    A(f"- **GUI sem conteúdo:** {sum(1 for r in gui if r['status']=='vazia')}/"
      f"{len(gui)} DBs ACP não têm mensagens do agente — prováveis sessões "
      "abandonadas no Kanban do Desktop ou janelas abertas sem prompt.")
    A(f"- **Rotatividade:** {len(orphan_locks)} session_ids existiram e foram "
      "removidas da DB (locks órfãos) — a app faz prune do histórico.")
    A("- **Causas de falha recorrentes:** comandos WSL/shell com exit≠0, "
      "paths Windows↔WSL misturados, greps sem match — ver secção 3.7.\n")

    A("## 6. Anexos\n")
    A("### 6.1 Lista completa de session_ids\n")
    A("**CLI (sessions.db):**\n")
    A("```")
    A(", ".join(sorted(ids_cli := {r['id'] for r in cli})))
    A("```\n")
    A("**GUI (acp-messages):**\n")
    A("```")
    A(", ".join(sorted(r["id"][:8] for r in gui)))
    A("```\n")
    A("### 6.2 🔍 Anomalias / Órfãs\n")
    A(f"**Locks sem session na DB** ({len(orphan_locks)}) — sessões que existiram "
      "(lock file) mas foram removidas/expiradas da `sessions` table:\n")
    A("```")
    A(", ".join(orphan_locks))
    A("```\n")
    recovered = sorted(set(orphan_locks) & set(mem_sessions))
    A(f"**Órfãs com prompts preservados em `.devin/memory/`** ({len(recovered)}) — "
      "conteúdo parcial recuperável via `session-<slug>.jsonl`:\n")
    A("```")
    A(", ".join(recovered) if recovered else "(nenhuma)")
    A("```\n")
    A("### 6.3 Consultas / comandos usados\n")
    A("```sql")
    A("-- inventário")
    A("SELECT name, type, sql FROM sqlite_master WHERE type IN ('table','index','view');")
    A("SELECT id,title,working_directory,backend_type,model,agent_mode,")
    A("       created_at,last_activity_at,hidden FROM sessions ORDER BY created_at;")
    A("SELECT session_id, chat_message, metadata FROM message_nodes")
    A("   ORDER BY session_id, node_id;")
    A("SELECT session_id, tool_call_json, tool_call_update_json FROM tool_call_state;")
    A("-- GUI")
    A("SELECT value FROM meta WHERE key='info';")
    A("SELECT kind, payload FROM messages ORDER BY CAST(position AS INT);")
    A("```")
    A("```bash")
    A("ls $APPDATA/devin/cli/            # sessions.db, logs/, summaries/, session_locks/")
    A("ls $APPDATA/devin/User/acp-messages/   # DBs GUI")
    A("ls .devin/memory/session-*.jsonl       # prompts logados por hooks")
    A("python scripts/audit_sessions.py       # pipeline completo")
    A("```\n")
    A("### 6.4 Fontes consultadas\n")
    A("| Fonte | Estado | Conteúdo extraído |")
    A("|---|---|---|")
    n_nodes = sum(r["user_msgs"] + r["assistant_msgs"] + r["tool_msgs"]
                  + r["system_msgs"] for r in cli)
    n_tcs = sum(r["tool_calls"] for r in cli)
    A(f"| `cli/sessions.db` (569 MB) | ✅ | {len(cli)} sessions, "
      f"~{n_nodes//1000}k message_nodes, {n_tcs} tool_call_state |")
    A(f"| `User/acp-messages/*.db` | ✅ | {len(gui)} DBs GUI "
      f"({sum(1 for r in gui if r['status']=='vazia')} vazias) |")
    A(f"| `cli/session_locks/*.lock` | ✅ | 301 locks, {len(orphan_locks)} órfãos |")
    if log_info:
        A(f"| `cli/logs/*.log.gz` | ✅ {log_info[2]} ficheiros | "
          f"janela {log_info[0]}→{log_info[1]} (não correlacionados por session_id) |")
    A(f"| `cli/summaries/*.md` | ✅ {n_summaries} ficheiros | "
      "resumos nomeados por hash (sem mapeamento direto p/ session_id) |")
    A(f"| `.devin/memory/session-*.jsonl` | ✅ {len(mem_sessions)} ficheiros | "
      "prompts do workspace PAS (hook prompt_logger) |")
    A("| `prompt_history` / `rendered_commits` / `subagent_heads` | ✅ | "
      "tabelas existem mas estão **vazias** |")
    A("| Billing / tokens | ❌ NÃO DISPONÍVEL | sem colunas de custo na DB; "
      "só `num_tokens_preceding` por nó |\n")
    A("### 6.5 Cobertura das métricas pedidas\n")
    A("| Métrica | Estado |")
    A("|---|---|")
    A("| session_id, datas, duração, workspace, modelo, prompt, msgs, tool calls, ferramentas, ficheiros | ✅ |")
    A("| Status final | ⚠️ inferido (DB não grava) |")
    A("| Tokens | ⚠️ parcial — só contexto máximo (`num_tokens_preceding`) |")
    A("| Custo / billing | ❌ sem dados na DB |")
    A("| PRs/commits/branches | ❌ não gravados na DB de sessões |")
    A("| Erros com stack trace | ⚠️ só tool calls `failed` (amostras em 3.7) |")
    A("| Link p/ logs | ⚠️ logs por arranque do app, não por session_id |\n")

    (WS / "sessions_report.md").write_text("\n".join(L), encoding="utf-8")


if __name__ == "__main__":
    main()
