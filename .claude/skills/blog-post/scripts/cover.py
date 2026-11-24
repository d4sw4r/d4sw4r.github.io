#!/usr/bin/env python3
"""Generate a blog cover (1536x1024) in the site's dark neon style.

Usage:
  python3 cover.py spec.json out_dir/
Writes out_dir/cover.svg and out_dir/cover.html; render with render.js.

spec.json:
{
  "title": "Part 4: ",            # white part of the headline
  "highlight": "Upgrades the GitOps Way",  # teal part (optional)
  "subtitle": "Talos Linux on Hetzner Bare Metal with Cilium",
  "pills": ["etcd snapshot", "upgrade-k8s --dry-run", "talosctl rollback"],  # 0-3
  "tagline": "pin · review · roll out · recover",
  "center_svg": "<g>...</g>",      # optional: custom SVG for the middle band
                                   # (area roughly x 60-1480, y 260-760)
  "seed": 7
}
Without center_svg a default row of glowing hexagons is drawn from
"nodes": [{"label": "Git", "sub": "merge"}, ...] (2-4 entries).
Available defs for center_svg: filters #glow, #bigglow, #lineglow (use
#lineglow on straight lines: #glow clips zero-height shapes); gradients #hexfill,
#flow (horizontal, userSpaceOnUse). Classes: .label .sub .mono .pill.
"""
import json, math, random, sys, os, html

W, H = 1536, 1024
spec = json.load(open(sys.argv[1]))
out = sys.argv[2] if len(sys.argv) > 2 else "."
os.makedirs(out, exist_ok=True)
random.seed(spec.get("seed", 7))
esc = html.escape

bg = []
for _ in range(260):
    x, y = random.uniform(0, W), random.uniform(0, H)
    r = random.choice([0.8, 1, 1.2, 1.6, 2.2])
    bg.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{r}" fill="#8fb4ff" opacity="{random.uniform(0.15,0.6):.2f}"/>')
for _ in range(34):
    x, y = random.uniform(0, W), random.uniform(0, H)
    pts = [(x, y)]
    for i in range(random.randint(2, 4)):
        if i % 2 == 0: x += random.choice([-1, 1]) * random.uniform(40, 160)
        else: y += random.choice([-1, 1]) * random.uniform(30, 110)
        pts.append((x, y))
    d = "M" + " L".join(f"{p[0]:.0f},{p[1]:.0f}" for p in pts)
    bg.append(f'<path d="{d}" stroke="#3b5ba8" stroke-width="1.4" fill="none" opacity="0.28"/>')
    bg.append(f'<circle cx="{pts[-1][0]:.0f}" cy="{pts[-1][1]:.0f}" r="3" fill="none" stroke="#4d73c9" opacity="0.4"/>')

def hexagon(cx, cy, r, label, sub=""):
    pts = " ".join(f"{cx+r*math.cos(math.radians(60*i-90)):.1f},{cy+r*math.sin(math.radians(60*i-90)):.1f}" for i in range(6))
    return (f'<g filter="url(#glow)"><polygon points="{pts}" fill="url(#hexfill)" stroke="#5fd4ff" stroke-width="3"/></g>'
            f'<text x="{cx}" y="{cy+12}" class="label" style="font-size:34px">{esc(label)}</text>'
            f'<text x="{cx}" y="{cy+r+44}" class="mono sub">{esc(sub)}</text>')

center = spec.get("center_svg")
if not center:
    nodes = spec.get("nodes", [{"label": "Git"}, {"label": "Flux"}, {"label": "Cluster"}])
    n = len(nodes); gap = 1100 / max(n - 1, 1); xs = [W/2 - 550 + i*gap for i in range(n)] if n > 1 else [W/2]
    parts = []
    for i in range(n - 1):
        x1, x2 = xs[i] + 100, xs[i+1] - 116
        parts.append(f'<path d="M{x1:.0f},480 L{x2:.0f},480" stroke="url(#flow)" stroke-width="3.5" filter="url(#lineglow)"/>')
        parts.append(f'<polygon points="{x2:.0f},471 {x2+16:.0f},480 {x2:.0f},489" fill="#7fffd4"/>')
    for x, nd in zip(xs, nodes):
        parts.append(hexagon(x, 480, 100, nd["label"], nd.get("sub", "")))
    center = "\n".join(parts)

pills = spec.get("pills", [])[:3]
pill_svg = []
if pills:
    pw, gap = 340, 50; total = len(pills)*pw + (len(pills)-1)*gap; x0 = W/2 - total/2
    for i, p in enumerate(pills):
        x = x0 + i*(pw+gap)
        pill_svg.append(f'<rect x="{x:.0f}" y="800" width="{pw}" height="62" rx="31" fill="#0f1834" stroke="#3f5fa8" stroke-width="2"/>'
                        f'<text x="{x+pw/2:.0f}" y="839" class="mono pill">{esc(p)}</text>')

hl = f'<tspan fill="#7fe8d6">{esc(spec["highlight"])}</tspan>' if spec.get("highlight") else ""
svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
<defs>
 <radialGradient id="bg" cx="50%" cy="45%" r="75%"><stop offset="0" stop-color="#16204a"/><stop offset="0.55" stop-color="#0b1130"/><stop offset="1" stop-color="#05081a"/></radialGradient>
 <linearGradient id="hexfill" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#1f3f8f"/><stop offset="1" stop-color="#132a63"/></linearGradient>
 <linearGradient id="flow" gradientUnits="userSpaceOnUse" x1="200" y1="0" x2="1336" y2="0"><stop offset="0" stop-color="#5fd4ff"/><stop offset="1" stop-color="#7fffd4"/></linearGradient>
 <filter id="glow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="5" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
 <filter id="lineglow" filterUnits="userSpaceOnUse" x="0" y="0" width="{W}" height="{H}"><feGaussianBlur stdDeviation="5" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
 <filter id="bigglow" x="-100%" y="-100%" width="300%" height="300%"><feGaussianBlur stdDeviation="14"/></filter>
 <style>
  text{{font-family:Inter,sans-serif;fill:#e8eeff;text-anchor:middle}}
  .mono{{font-family:'JetBrains Mono',monospace}}
  .label{{font-size:30px;font-weight:600}}
  .sub{{font-size:21px;fill:#8fa8d8}}
  .pill{{font-size:22px;fill:#cfe0ff}}
 </style>
</defs>
<rect width="{W}" height="{H}" fill="url(#bg)"/>
{chr(10).join(bg)}
<text x="{W/2}" y="118" style="font-size:66px;font-weight:600">{esc(spec.get("title",""))}{hl}</text>
<text x="{W/2}" y="172" style="font-size:26px;fill:#93a6d1;font-weight:500">{esc(spec.get("subtitle",""))}</text>
<line x1="{W/2-330}" y1="212" x2="{W/2-60}" y2="212" stroke="#4d73c9" stroke-width="2" opacity="0.7"/>
<line x1="{W/2+60}" y1="212" x2="{W/2+330}" y2="212" stroke="#4d73c9" stroke-width="2" opacity="0.7"/>
<circle cx="{W/2}" cy="212" r="6" fill="#7fe8d6" filter="url(#glow)"/>
{center}
{"".join(pill_svg)}
<text x="{W/2}" y="950" style="font-size:24px;fill:#6f84b5;font-weight:500">{esc(spec.get("tagline",""))}</text>
</svg>'''
open(os.path.join(out, "cover.svg"), "w").write(svg)
open(os.path.join(out, "cover.html"), "w").write(f'<html><body style="margin:0;background:#05081a">{svg}</body></html>')
print(os.path.join(out, "cover.html"))
