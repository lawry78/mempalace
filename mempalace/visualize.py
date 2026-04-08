"""
visualize.py — Palace Map + Dashboard visualization.

Generates a self-contained HTML file with:
  - Summary stats (drawers, wings, rooms, KG entities)
  - Interactive force-directed graph (rooms as nodes, tunnels as edges)
  - Wing/room breakdown table

Zero external dependencies — vanilla JS + Canvas, works offline.

Usage:
    from mempalace.visualize import generate_visualization
    html = generate_visualization(output_path="palace_map.html")
"""

import json
import os
import tempfile
from datetime import datetime

import chromadb
from chromadb.errors import InvalidCollectionException

from .config import MempalaceConfig, DEFAULT_COLLECTION_NAME
from .collection_utils import iter_all_metadata
from .palace_graph import build_graph
from .knowledge_graph import KnowledgeGraph


def collect_data(palace_path=None, kg_db_path=None):
    """Collect all data needed for visualization."""
    cfg = MempalaceConfig()
    palace_path = palace_path or cfg.palace_path

    data = {
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "palace_path": palace_path,
        "total_drawers": 0,
        "wings": {},
        "rooms": {},
        "graph_nodes": {},
        "graph_edges": [],
        "kg_stats": {"entities": 0, "triples": 0, "active_triples": 0},
    }

    try:
        client = chromadb.PersistentClient(path=palace_path)
        col = client.get_collection(DEFAULT_COLLECTION_NAME)
    except (InvalidCollectionException, ValueError):
        data["error"] = "No palace found"
        return data

    data["total_drawers"] = col.count()

    # Wing/room counts
    for m in iter_all_metadata(col):
        w = m.get("wing", "unknown")
        r = m.get("room", "unknown")
        data["wings"][w] = data["wings"].get(w, 0) + 1
        key = f"{w}/{r}"
        data["rooms"][key] = data["rooms"].get(key, 0) + 1

    # Graph
    nodes, edges = build_graph(col=col)
    data["graph_nodes"] = nodes
    data["graph_edges"] = edges

    # KG stats
    try:
        kg = KnowledgeGraph(db_path=kg_db_path) if kg_db_path else KnowledgeGraph()
        data["kg_stats"] = kg.stats()
    except Exception:
        pass

    return data


def create_demo_palace():
    """Create a temporary palace with realistic demo data. Returns palace_path."""
    demo_path = os.path.join(tempfile.mkdtemp(prefix="mempalace_demo_"), "palace")
    os.makedirs(demo_path, exist_ok=True)
    client = chromadb.PersistentClient(path=demo_path)
    col = client.get_or_create_collection(DEFAULT_COLLECTION_NAME)

    drawers = [
        ("JWT tokens handle session auth. Refresh tokens in HttpOnly cookies. 24h expiry.", "project_mempalace", "backend", "hall_facts", "auth.py"),
        ("Database migrations via Alembic. PostgreSQL 15 + pgbouncer pooling.", "project_mempalace", "backend", "hall_facts", "db.py"),
        ("Switched from REST to GraphQL for the dashboard API.", "project_mempalace", "backend", "hall_decisions", "api.py"),
        ("React frontend with TanStack Query for server state.", "project_mempalace", "frontend", "hall_facts", "App.tsx"),
        ("Migrated from CRA to Vite. Build time dropped from 45s to 3s.", "project_mempalace", "frontend", "hall_discoveries", "vite.config.ts"),
        ("ChromaDB stores all drawers with wing/room metadata.", "project_mempalace", "chromadb-setup", "hall_facts", "searcher.py"),
        ("Palace graph connects rooms across wings via tunnels.", "project_mempalace", "chromadb-setup", "hall_facts", "palace_graph.py"),
        ("Sprint planning: migrate auth to passkeys by Q3.", "project_mempalace", "planning", "hall_events", "sprint.md"),
        ("Decided to keep ChromaDB over Pinecone — local-first principle.", "project_mempalace", "planning", "hall_decisions", "adr-003.md"),
        ("AAAK dialect compresses entities into 3-letter codes.", "project_mempalace", "aaak-dialect", "hall_discoveries", "dialect.py"),
        ("Alice is the project lead. Started MemPalace in January 2025.", "wing_alice", "identity", "hall_facts", "intro.txt"),
        ("Alice prefers functional programming. Hates unnecessary abstractions.", "wing_alice", "preferences", "hall_preferences", "notes.txt"),
        ("Alice debugged the SQLite variable limit bug.", "wing_alice", "backend", "hall_events", "debug-log.txt"),
        ("Alice presented MemPalace at the local Python meetup.", "wing_alice", "milestones", "hall_events", "journal.txt"),
        ("Max is 11, loves chess and swimming.", "wing_max", "identity", "hall_facts", "family.txt"),
        ("Max won the regional chess tournament.", "wing_max", "milestones", "hall_events", "family.txt"),
        ("Max asked about how AI memory works.", "wing_max", "conversations", "hall_discoveries", "chat.txt"),
        ("GPU pricing: RTX 4090 vs A100 for local inference.", "wing_hardware", "gpu-pricing", "hall_facts", "research.md"),
        ("Ordered 2x RTX 4090 for the home lab.", "wing_hardware", "gpu-pricing", "hall_events", "orders.md"),
        ("M2 Ultra: ChromaDB + MemPalace runs LongMemEval in 4.5 min.", "wing_hardware", "benchmarks", "hall_discoveries", "bench.md"),
        ("Home server: 64GB RAM, 2TB NVMe. Runs ChromaDB + Ollama 24/7.", "wing_hardware", "homelab", "hall_facts", "setup.md"),
        ("LongMemEval: 96.6% R@5 in raw mode. Zero API calls.", "wing_ai_research", "benchmarks", "hall_facts", "longmemeval.md"),
        ("RAG with structured metadata outperforms naive vector search by 34%.", "wing_ai_research", "benchmarks", "hall_discoveries", "rag-study.md"),
        ("Temporal KG tracks when facts change with valid_from/valid_to.", "wing_ai_research", "knowledge-graphs", "hall_facts", "kg-design.md"),
        ("Entity detection without LLM: verb patterns + pronoun proximity.", "wing_ai_research", "entity-detection", "hall_discoveries", "detector.md"),
        ("Alice reviewed benchmark results and confirmed the 96.6% score.", "wing_alice", "benchmarks", "hall_events", "review.txt"),
        ("Backend auth needs to work with new passkey standard.", "wing_alice", "backend", "hall_facts", "auth-research.txt"),
        ("KG now tracks Alice, Max, and all project entities.", "wing_ai_research", "knowledge-graphs", "hall_facts", "kg-entities.md"),
    ]

    dates = [
        "2025-01-15", "2025-02-01", "2025-03-10", "2025-04-01", "2025-05-15",
        "2025-06-01", "2025-07-20", "2025-08-10", "2025-09-01", "2025-10-15",
        "2025-11-01", "2025-12-01", "2026-01-10", "2026-02-01", "2026-03-01",
    ]

    ids, docs, metas = [], [], []
    for i, (doc, wing, room, hall, source) in enumerate(drawers):
        ids.append(f"demo_{wing}_{room}_{i}")
        docs.append(doc)
        metas.append({
            "wing": wing, "room": room, "hall": hall,
            "source_file": source, "chunk_index": 0, "added_by": "demo",
            "filed_at": f"{dates[i % len(dates)]}T12:00:00",
            "date": dates[i % len(dates)],
        })

    col.add(ids=ids, documents=docs, metadatas=metas)
    return demo_path


def generate_visualization(palace_path=None, kg_db_path=None, output_path=None, demo=False):
    """Generate a self-contained HTML visualization.

    Returns:
        dict with "html" string and optionally "output_path".
    """
    if demo:
        palace_path = create_demo_palace()
    data = collect_data(palace_path=palace_path, kg_db_path=kg_db_path)
    html = _build_html(data)

    result = {"html": html, "data": data}

    if output_path:
        output_path = os.path.expanduser(output_path)
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)
        result["output_path"] = output_path

    return result


def _build_html(data):
    """Build the complete HTML string with embedded data."""
    data_json = json.dumps(data, indent=None, default=str)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>MemPalace — Palace Map</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0a0a0f; color: #e0e0e0; }}
.header {{ padding: 24px 32px; background: #12121a; border-bottom: 1px solid #2a2a3a; }}
.header h1 {{ font-size: 24px; color: #a78bfa; margin-bottom: 4px; }}
.header .sub {{ font-size: 13px; color: #666; }}
.stats {{ display: flex; gap: 24px; padding: 20px 32px; background: #0f0f18; flex-wrap: wrap; }}
.stat {{ background: #16162a; border-radius: 8px; padding: 16px 24px; min-width: 140px; }}
.stat .num {{ font-size: 28px; font-weight: 700; color: #a78bfa; }}
.stat .label {{ font-size: 12px; color: #888; margin-top: 4px; }}
.graph-section {{ padding: 16px 32px; }}
.graph-section h2 {{ font-size: 16px; color: #a78bfa; margin-bottom: 12px; }}
#graph-container {{ width: 100%; height: 480px; background: #0c0c14; border-radius: 8px; border: 1px solid #1e1e30; position: relative; cursor: grab; }}
#graph-container:active {{ cursor: grabbing; }}
#tooltip {{ position: absolute; display: none; background: #1a1a2e; border: 1px solid #3a3a5a; border-radius: 10px; padding: 0; font-size: 13px; pointer-events: none; z-index: 10; min-width: 260px; max-width: 380px; box-shadow: 0 8px 32px rgba(0,0,0,0.5); overflow: hidden; }}
#tooltip .tt-header {{ background: #252540; padding: 12px 16px; border-bottom: 1px solid #3a3a5a; }}
#tooltip .tt-title {{ font-weight: 700; font-size: 15px; color: #a78bfa; }}
#tooltip .tt-subtitle {{ font-size: 11px; color: #666; margin-top: 2px; }}
#tooltip .tt-body {{ padding: 12px 16px; }}
#tooltip .tt-table {{ width: 100%; border-collapse: collapse; }}
#tooltip .tt-table td {{ padding: 5px 0; vertical-align: top; }}
#tooltip .tt-table td:first-child {{ color: #666; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; width: 70px; padding-right: 12px; }}
#tooltip .tt-table td:last-child {{ color: #ccc; }}
#tooltip .tt-badge {{ display: inline-block; background: #2a2a4a; border-radius: 4px; padding: 2px 8px; margin: 1px 2px; font-size: 11px; color: #a78bfa; }}
#tooltip .tt-bar-bg {{ height: 6px; background: #2a2a3a; border-radius: 3px; margin-top: 8px; }}
#tooltip .tt-bar {{ height: 6px; border-radius: 3px; background: #a78bfa; }}
.legend {{ display: flex; gap: 12px; flex-wrap: wrap; padding: 8px 0; }}
.legend-item {{ display: flex; align-items: center; gap: 6px; font-size: 12px; color: #888; }}
.legend-dot {{ width: 10px; height: 10px; border-radius: 50%; }}
.table-section {{ padding: 16px 32px 32px; }}
.table-section h2 {{ font-size: 16px; color: #a78bfa; margin-bottom: 12px; }}
table {{ width: 100%; border-collapse: collapse; }}
th {{ text-align: left; padding: 8px 12px; border-bottom: 2px solid #2a2a3a; color: #888; font-size: 12px; font-weight: 600; text-transform: uppercase; }}
td {{ padding: 8px 12px; border-bottom: 1px solid #1a1a2a; font-size: 13px; }}
tr:hover td {{ background: #16162a; }}
.bar {{ height: 6px; border-radius: 3px; background: #a78bfa; display: inline-block; vertical-align: middle; margin-left: 8px; }}
.empty {{ text-align: center; padding: 60px; color: #555; }}
</style>
</head>
<body>

<div class="header">
  <h1>MemPalace Map</h1>
  <div class="sub">Generated <span id="gen-date"></span> &mdash; <span id="palace-path"></span></div>
</div>

<div class="stats" id="stats-row"></div>

<div class="graph-section">
  <h2>Palace Graph</h2>
  <div class="legend" id="legend"></div>
  <div id="graph-container">
    <canvas id="graph"></canvas>
    <div id="tooltip"></div>
  </div>
</div>

<div class="table-section">
  <h2>Wing / Room Breakdown</h2>
  <div id="table-container"></div>
</div>

<script>
const DATA = {data_json};

// ── Dashboard stats ──────────────────────────────────────────────
document.getElementById('gen-date').textContent = DATA.generated;
document.getElementById('palace-path').textContent = DATA.palace_path;

const statsRow = document.getElementById('stats-row');
const stats = [
  {{ num: DATA.total_drawers, label: 'Total Drawers' }},
  {{ num: Object.keys(DATA.wings).length, label: 'Wings' }},
  {{ num: Object.keys(DATA.graph_nodes).length, label: 'Rooms' }},
  {{ num: DATA.graph_edges.length, label: 'Tunnels' }},
  {{ num: DATA.kg_stats.entities || 0, label: 'KG Entities' }},
  {{ num: DATA.kg_stats.active_triples || 0, label: 'KG Active Facts' }},
];
stats.forEach(s => {{
  const div = document.createElement('div');
  div.className = 'stat';
  div.innerHTML = `<div class="num">${{s.num}}</div><div class="label">${{s.label}}</div>`;
  statsRow.appendChild(div);
}});

// ── Wing colors ──────────────────────────────────────────────────
const COLORS = ['#a78bfa','#f472b6','#34d399','#fbbf24','#60a5fa','#f87171','#2dd4bf','#fb923c','#a3e635','#c084fc'];
const wingList = Object.keys(DATA.wings).sort();
const wingColor = {{}};
wingList.forEach((w, i) => wingColor[w] = COLORS[i % COLORS.length]);

const legend = document.getElementById('legend');
wingList.forEach(w => {{
  const el = document.createElement('span');
  el.className = 'legend-item';
  el.innerHTML = `<span class="legend-dot" style="background:${{wingColor[w]}}"></span>${{w}} (${{DATA.wings[w]}})`;
  legend.appendChild(el);
}});

// ── Force-directed graph ─────────────────────────────────────────
const container = document.getElementById('graph-container');
const canvas = document.getElementById('graph');
const ctx = canvas.getContext('2d');
const tooltip = document.getElementById('tooltip');

function resize() {{
  canvas.width = container.clientWidth;
  canvas.height = container.clientHeight;
}}
resize();
window.addEventListener('resize', () => {{ resize(); draw(); }});

// Build nodes
const nodes = [];
const nodeMap = {{}};
Object.entries(DATA.graph_nodes).forEach(([room, info]) => {{
  const wings = info.wings || [];
  const r = Math.max(8, Math.min(40, Math.sqrt(info.count) * 3));
  const node = {{
    id: room,
    label: room,
    wings: wings,
    count: info.count,
    halls: info.halls || [],
    dates: info.dates || [],
    color: wings.length > 0 ? wingColor[wings[0]] || '#666' : '#666',
    r: r,
    x: canvas.width/2 + (Math.random()-0.5)*300,
    y: canvas.height/2 + (Math.random()-0.5)*300,
    vx: 0, vy: 0,
  }};
  nodes.push(node);
  nodeMap[room] = node;
}});

// Build edges
const edges = [];
DATA.graph_edges.forEach(e => {{
  // Edge connects rooms across wings — find rooms in both wings
  const src = nodeMap[e.room];
  if (!src) return;
  // Create edges to other rooms in the target wing
  Object.entries(DATA.graph_nodes).forEach(([otherRoom, info]) => {{
    if (otherRoom === e.room) return;
    if (info.wings && info.wings.includes(e.wing_b)) {{
      if (!edges.find(x => (x.src===e.room && x.dst===otherRoom) || (x.src===otherRoom && x.dst===e.room))) {{
        edges.push({{ src: e.room, dst: otherRoom }});
      }}
    }}
  }});
}});

// If no tunnel edges, connect rooms that share a wing
if (edges.length === 0) {{
  const wingRooms = {{}};
  nodes.forEach(n => n.wings.forEach(w => {{
    if (!wingRooms[w]) wingRooms[w] = [];
    wingRooms[w].push(n.id);
  }}));
  Object.values(wingRooms).forEach(rooms => {{
    for (let i = 0; i < rooms.length && i < 8; i++) {{
      for (let j = i+1; j < rooms.length && j < 8; j++) {{
        if (!edges.find(e => (e.src===rooms[i]&&e.dst===rooms[j])||(e.src===rooms[j]&&e.dst===rooms[i]))) {{
          edges.push({{ src: rooms[i], dst: rooms[j] }});
        }}
      }}
    }}
  }});
}}

// Simple force simulation
function simulate() {{
  const W = canvas.width, H = canvas.height;
  // Repulsion between all nodes
  for (let i = 0; i < nodes.length; i++) {{
    for (let j = i+1; j < nodes.length; j++) {{
      let dx = nodes[j].x - nodes[i].x;
      let dy = nodes[j].y - nodes[i].y;
      let d = Math.sqrt(dx*dx + dy*dy) || 1;
      let force = 800 / (d * d);
      nodes[i].vx -= dx/d * force;
      nodes[i].vy -= dy/d * force;
      nodes[j].vx += dx/d * force;
      nodes[j].vy += dy/d * force;
    }}
  }}
  // Attraction along edges
  edges.forEach(e => {{
    const a = nodeMap[e.src], b = nodeMap[e.dst];
    if (!a || !b) return;
    let dx = b.x - a.x, dy = b.y - a.y;
    let d = Math.sqrt(dx*dx+dy*dy) || 1;
    let force = (d - 100) * 0.005;
    a.vx += dx/d * force;
    a.vy += dy/d * force;
    b.vx -= dx/d * force;
    b.vy -= dy/d * force;
  }});
  // Center gravity
  nodes.forEach(n => {{
    n.vx += (W/2 - n.x) * 0.001;
    n.vy += (H/2 - n.y) * 0.001;
    n.vx *= 0.9;
    n.vy *= 0.9;
    n.x += n.vx;
    n.y += n.vy;
    n.x = Math.max(n.r, Math.min(W-n.r, n.x));
    n.y = Math.max(n.r, Math.min(H-n.r, n.y));
  }});
}}

function draw() {{
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  // Edges
  ctx.strokeStyle = '#2a2a4a';
  ctx.lineWidth = 1;
  edges.forEach(e => {{
    const a = nodeMap[e.src], b = nodeMap[e.dst];
    if (!a || !b) return;
    ctx.beginPath();
    ctx.moveTo(a.x, a.y);
    ctx.lineTo(b.x, b.y);
    ctx.stroke();
  }});
  // Nodes
  nodes.forEach(n => {{
    ctx.beginPath();
    ctx.arc(n.x, n.y, n.r, 0, Math.PI*2);
    ctx.fillStyle = n.color + '33';
    ctx.fill();
    ctx.strokeStyle = n.color;
    ctx.lineWidth = 2;
    ctx.stroke();
    // Label
    if (n.r > 10) {{
      ctx.fillStyle = '#ccc';
      ctx.font = `${{Math.min(11, n.r*0.7)}}px sans-serif`;
      ctx.textAlign = 'center';
      ctx.fillText(n.label, n.x, n.y + n.r + 14);
    }}
  }});
}}

// Animate
let frame = 0;
function tick() {{
  if (frame < 300) {{ simulate(); frame++; }}
  draw();
  requestAnimationFrame(tick);
}}
if (nodes.length > 0) tick();
else {{
  ctx.fillStyle = '#555';
  ctx.font = '16px sans-serif';
  ctx.textAlign = 'center';
  ctx.fillText('No rooms to display. Mine some files first.', canvas.width/2, canvas.height/2);
}}

// Tooltip on hover
canvas.addEventListener('mousemove', e => {{
  const rect = canvas.getBoundingClientRect();
  const mx = e.clientX - rect.left, my = e.clientY - rect.top;
  let hit = null;
  for (const n of nodes) {{
    const dx = mx - n.x, dy = my - n.y;
    if (dx*dx + dy*dy < n.r*n.r) {{ hit = n; break; }}
  }}
  if (hit) {{
    tooltip.style.display = 'block';
    // Position tooltip — keep within canvas bounds
    let tx = hit.x + hit.r + 14;
    let ty = hit.y - 20;
    if (tx + 300 > canvas.width) tx = hit.x - hit.r - 290;
    if (ty < 10) ty = 10;
    tooltip.style.left = tx + 'px';
    tooltip.style.top = ty + 'px';

    const maxCount = Math.max(...nodes.map(n => n.count));
    const barPct = Math.round((hit.count / maxCount) * 100);
    const wingBadges = hit.wings.map(w => `<span class="tt-badge" style="border-left:3px solid ${{wingColor[w] || '#666'}}">${{w}}</span>`).join(' ');
    const hallBadges = hit.halls.length ? hit.halls.map(h => `<span class="tt-badge">${{h}}</span>`).join(' ') : '<span style="color:#555">none</span>';
    const lastDate = hit.dates.length ? hit.dates[hit.dates.length - 1] : 'n/a';

    tooltip.innerHTML = `<div class="tt-header"><div class="tt-title">${{hit.label}}</div><div class="tt-subtitle">${{hit.count}} drawers &middot; last: ${{lastDate}}</div></div>`
      + `<div class="tt-body"><table class="tt-table">`
      + `<tr><td>Wings</td><td>${{wingBadges}}</td></tr>`
      + `<tr><td>Halls</td><td>${{hallBadges}}</td></tr>`
      + `<tr><td>Size</td><td>${{hit.count}} drawers<div class="tt-bar-bg"><div class="tt-bar" style="width:${{barPct}}%;background:${{hit.color}}"></div></div></td></tr>`
      + `</table></div>`;
  }} else {{
    tooltip.style.display = 'none';
  }}
}});

// Drag nodes
let dragNode = null;
canvas.addEventListener('mousedown', e => {{
  const rect = canvas.getBoundingClientRect();
  const mx = e.clientX - rect.left, my = e.clientY - rect.top;
  for (const n of nodes) {{
    const dx = mx - n.x, dy = my - n.y;
    if (dx*dx + dy*dy < n.r*n.r) {{ dragNode = n; break; }}
  }}
}});
canvas.addEventListener('mousemove', e => {{
  if (!dragNode) return;
  const rect = canvas.getBoundingClientRect();
  dragNode.x = e.clientX - rect.left;
  dragNode.y = e.clientY - rect.top;
  dragNode.vx = 0; dragNode.vy = 0;
}});
canvas.addEventListener('mouseup', () => {{ dragNode = null; }});

// ── Table ────────────────────────────────────────────────────────
const tableContainer = document.getElementById('table-container');
const entries = Object.entries(DATA.rooms).sort((a,b) => b[1]-a[1]);
if (entries.length === 0) {{
  tableContainer.innerHTML = '<div class="empty">No drawers filed yet.</div>';
}} else {{
  const maxCount = entries[0][1];
  let html = '<table><thead><tr><th>Wing</th><th>Room</th><th>Drawers</th><th></th></tr></thead><tbody>';
  entries.forEach(([key, count]) => {{
    const [wing, room] = key.split('/');
    const barW = Math.max(4, (count / maxCount) * 200);
    const color = wingColor[wing] || '#666';
    html += `<tr><td style="color:${{color}}">${{wing}}</td><td>${{room}}</td><td>${{count}}</td><td><span class="bar" style="width:${{barW}}px;background:${{color}}"></span></td></tr>`;
  }});
  html += '</tbody></table>';
  tableContainer.innerHTML = html;
}}
</script>
</body>
</html>"""
