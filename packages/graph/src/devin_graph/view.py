"""GR-2: self-contained HTML viewer for graph.db.

``devin-graph view`` renders the graph (or a filtered slice) into a single
HTML file: embedded JSON + a small vanilla-JS force layout on SVG. No CDN,
no external assets — it works offline by design, which is the whole point
of the ecosystem. Large graphs are downsampled: ``--limit`` caps nodes and
the viewer warns when it truncated.
"""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

_KIND_COLORS = {
    "session": "#4f8ef7",
    "project": "#f7a94f",
    "file": "#5cb870",
    "tool": "#b06ef7",
    "tool_call": "#7a8599",
    "commit": "#f75f5f",
    "gui_session": "#4fc3c3",
}

_PAGE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>devin-graph view</title>
<style>
 body{{font-family:system-ui,sans-serif;margin:0;background:#0e1116;color:#dde3ee}}
 header{{padding:10px 16px;border-bottom:1px solid #2a3242;font-size:13px}}
 #stats{{color:#8b96ab}}
 svg{{display:block;width:100vw;height:calc(100vh - 46px)}}
 circle{{stroke:#0e1116;stroke-width:1}}
 line{{stroke:#2a3242;stroke-width:.6;opacity:.7}}
 #tip{{position:fixed;pointer-events:none;background:#1c2330;border:1px solid #3a4458;
      padding:6px 9px;border-radius:4px;font-size:12px;display:none;max-width:420px}}
 #legend span{{display:inline-block;margin-right:12px}}
 .dot{{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:4px}}
 #filter{{margin-left:14px;background:#1c2330;color:#dde3ee;border:1px solid #3a4458;
          border-radius:4px;padding:3px 6px}}
</style></head><body>
<header><b>devin-graph</b> — {title}
 <select id="filter"><option value="">all kinds</option>{options}</select>
 <span id="stats"></span></header>
<div id="legend" style="padding:6px 16px;font-size:12px">{legend}</div>
<svg id="g"></svg><div id="tip"></div>
<script>
const DATA = {data};
const nodes = DATA.nodes, edges = DATA.edges;
const idx = new Map(nodes.map((n,i)=>[n.id,i]));
const links = edges.filter(e=>idx.has(e.source)&&idx.has(e.target))
  .map(e=>({{s:idx.get(e.source),t:idx.get(e.target)}}));
const svg = document.getElementById('g'), tip = document.getElementById('tip');
const W=innerWidth,H=innerHeight-46;
nodes.forEach((n,i)=>{{n.x=W/2+Math.cos(i)*80+Math.random()*40;
  n.y=H/2+Math.sin(i)*80+Math.random()*40;n.vx=0;n.vy=0;}});
const NS='http://www.w3.org/2000/svg';
const gLines=document.createElementNS(NS,'g'),gNodes=document.createElementNS(NS,'g');
svg.appendChild(gLines);svg.appendChild(gNodes);
const lEls=links.map(l=>{{const e=document.createElementNS(NS,'line');gLines.appendChild(e);return e;}});
const nEls=nodes.map((n,i)=>{{const c=document.createElementNS(NS,'circle');
  c.setAttribute('r',n.kind==='session'?6:(n.kind==='project'?7:4));
  c.setAttribute('fill',DATA.colors[n.kind]||'#8b96ab');
  c.onmousemove=ev=>{{tip.style.display='block';tip.style.left=ev.clientX+12+'px';
    tip.style.top=ev.clientY+12+'px';tip.innerHTML=n.tip;}};
  c.onmouseleave=()=>tip.style.display='none';
  gNodes.appendChild(c);return c;}});
function tick(){{
 for(let i=0;i<nodes.length;i++)for(let j=i+1;j<nodes.length;j++){{
  const a=nodes[i],b=nodes[j];let dx=a.x-b.x,dy=a.y-b.y,d2=dx*dx+dy*dy+0.01;
  if(d2<40000){{const f=30/d2;a.vx+=dx*f;b.vx-=dx*f;a.vy+=dy*f;b.vy-=dy*f;}}}}
 for(const l of links){{const a=nodes[l.s],b=nodes[l.t];
  let dx=b.x-a.x,dy=b.y-a.y,d=Math.sqrt(dx*dx+dy*dy)||1,f=(d-60)/d*0.04;
  a.vx+=dx*f;b.vx-=dx*f;a.vy+=dy*f;b.vy-=dy*f;}}
 for(const n of nodes){{n.vx+=(W/2-n.x)*0.0005;n.vy+=(H/2-n.y)*0.0005;
  n.vx*=0.85;n.vy*=0.85;n.x+=n.vx;n.y+=n.vy;}}
 lEls.forEach((e,i)=>{{const l=links[i];
  e.setAttribute('x1',nodes[l.s].x);e.setAttribute('y1',nodes[l.s].y);
  e.setAttribute('x2',nodes[l.t].x);e.setAttribute('y2',nodes[l.t].y);}});
 nEls.forEach((e,i)=>{{e.setAttribute('cx',nodes[i].x);e.setAttribute('cy',nodes[i].y);}});
}}
let frames=0;
(function loop(){{tick();if(++frames<400)requestAnimationFrame(loop);}})();
document.getElementById('stats').textContent=
 ` · ${{nodes.length}} nodes · ${{links.length}} edges${{DATA.truncated?' · TRUNCATED (--limit)':''}}`;
document.getElementById('filter').onchange=ev=>{{
 const k=ev.target.value;
 nEls.forEach((e,i)=>{{e.style.opacity=(!k||nodes[i].kind===k)?1:0.08;}});
 lEls.forEach((e,i)=>{{const l=links[i];
  e.style.opacity=(!k||nodes[l.s].kind===k||nodes[l.t].kind===k)?0.7:0.04;}});
}};
</script></body></html>"""


def render_view(export: dict[str, Any], *, limit: int = 500,
                seed: int = 42) -> str:
    """graph.db export dict → self-contained HTML page."""
    nodes = export.get("nodes", [])
    edges = export.get("edges", [])
    truncated = len(nodes) > limit
    if truncated:
        # keep the highest-degree nodes so the slice stays meaningful
        degree: dict[str, int] = {}
        for e in edges:
            degree[e["source"]] = degree.get(e["source"], 0) + 1
            degree[e["target"]] = degree.get(e["target"], 0) + 1
        keep = {n["id"] for n in sorted(
            nodes, key=lambda n: -degree.get(n["id"], 0))[:limit]}
        nodes = [n for n in nodes if n["id"] in keep]
        edges = [e for e in edges
                 if e["source"] in keep and e["target"] in keep]

    view_nodes = [{
        "id": n["id"], "kind": n["kind"],
        "tip": ("<b>" + html.escape(n["kind"]) + "</b> "
                + html.escape(str(n.get("key", n["id"]))[:200])),
    } for n in nodes]
    data = {
        "nodes": view_nodes,
        "edges": edges,
        "colors": _KIND_COLORS,
        "truncated": truncated,
    }
    kinds = sorted({n["kind"] for n in view_nodes})
    legend = "".join(
        f'<span><span class="dot" style="background:{_KIND_COLORS.get(k, "#8b96ab")}"></span>{k}</span>'
        for k in kinds)
    options = "".join(f'<option value="{k}">{k}</option>' for k in kinds)
    src = export.get("meta", {}).get("source_db", "graph.db")
    return _PAGE.format(
        title=html.escape(src),
        data=json.dumps(data, separators=(",", ":")),
        legend=legend, options=options)


def write_view(export: dict[str, Any], out: str | Path,
               limit: int = 500) -> Path:
    p = Path(out).expanduser()
    p.write_text(render_view(export, limit=limit), encoding="utf-8")
    return p
