#!/usr/bin/env python3
"""Render the 'recursive zoom' hero animation (dark + light) as static SVGs.

Three scenes, each nested inside the previous one:
  input -> f -> output   (zoom into f)
  the network inside f   (zoom into one layer)
  that layer's activation manifold (zoom into one point -> it is an input again)

Every scene is the full frame scaled about the previous scene's zoom target, and
both scenes zoom by the same factor at the same time, so the handoff reads as one
continuous camera move. Pure SVG + CSS/SMIL, no JS (GitHub strips it anyway).
"""
import math
import os
import random

OUT = os.path.join(os.path.dirname(__file__), "..", "assets")
W, H = 840, 300
T = 15.0            # loop length, seconds
ZOOM = 8.0          # how far a scene zooms past the camera on exit
STEPS = 8           # keyframes per zoom segment (approximates exponential zoom)

THEMES = {
    "dark": dict(bg="#0d1117", panel="#161b22", border="#30363d", fg="#e6edf3",
                 muted="#8b949e", key="#c084fc", accent="#f472b6", cool="#60a5fa", ok="#4ade80"),
    "light": dict(bg="#ffffff", panel="#f6f8fa", border="#d0d7de", fg="#1f2328",
                  muted="#59636e", key="#7c3aed", accent="#db2777", cool="#2563eb", ok="#16a34a"),
}

# Scene windows as fractions of T: (hold_start, hold_end) then a zoom to the next.
HOLD = 0.233
SEG = 1 / 3


def about(p, s):
    """CSS transform that scales by s about point p (with transform-origin 0 0)."""
    x, y = p
    return f"translate({x * (1 - s):.2f}px,{y * (1 - s):.2f}px) scale({s:.4f})"


def scene_keyframes(name, i, enter_from, target):
    """Keyframes for scene i (0..2): zoom in from tiny about `enter_from`, hold,
    zoom out past the camera about `target`, then sit invisible until next loop."""
    a = i * SEG
    zoom_len = SEG - HOLD
    ev = []
    for k in range(STEPS + 1):                      # entry: 1/ZOOM -> 1
        f = k / STEPS
        ev.append((a - zoom_len + f * zoom_len, ZOOM ** (f - 1), min(1.0, f * 2.2), enter_from))
    ev.append((a + HOLD, 1.0, 1.0, target))         # hold
    for k in range(1, STEPS + 1):                   # exit: 1 -> ZOOM
        f = k / STEPS
        ev.append((a + HOLD + f * zoom_len, ZOOM ** f, max(0.0, 1 - f ** 1.6), target))
    ev.append((a + SEG + 0.0005, 1 / ZOOM, 0.0, enter_from))   # park (invisible jump)
    frames = {}
    for t, sc, op, p in ev:
        frames[round((t % 1.0) * 100, 3)] = f"transform:{about(p, sc)};opacity:{op:.3f}"
    edge = frames[0.0] if i == 0 else f"transform:{about(enter_from, 1 / ZOOM)};opacity:0.000"
    frames[0.0] = frames[100.0] = edge
    body = "".join(f"{k:g}%{{{v}}}" for k, v in sorted(frames.items()))
    return f"@keyframes {name}{{{body}}}"


def caption_keyframes(name, i):
    a = i * SEG
    if i == 0:
        pts = {0: 1, HOLD: 1, HOLD + 0.02: 0, 0.97: 0, 1: 1}
    else:
        pts = {0: 0, a: 0, a + 0.03: 1, a + HOLD: 1, a + HOLD + 0.02: 0, 1: 0}
    return f"@keyframes {name}{{" + "".join(f"{k * 100:.2f}%{{opacity:{v}}}" for k, v in sorted(pts.items())) + "}"


# ---------------------------------------------------------------- scene A: x -> f -> f(x)
A_TARGET = (420, 150)


def scene_io(t):
    chips = []
    x = 92
    for word in ("the", "cat", "sat", "on"):
        w = 14 + len(word) * 9.5
        chips.append(f'<rect x="{x}" y="136" width="{w:.0f}" height="28" rx="6" fill="{t["panel"]}" stroke="{t["border"]}"/>'
                     f'<text x="{x + w / 2:.1f}" y="155" text-anchor="middle" fill="{t["fg"]}">{word}</text>')
        x += w + 6
    in_end = x
    return f"""
<text x="92" y="122" class="lbl" fill="{t['muted']}">input x</text>
{''.join(chips)}
<path id="ioPath" d="M{in_end + 6} 150 H 352 M 488 150 H 586" stroke="{t['border']}" stroke-width="2" fill="none"/>
<path d="M346 144 l8 6 l-8 6 M580 144 l8 6 l-8 6" stroke="{t['muted']}" stroke-width="2" fill="none"/>
<rect x="360" y="112" width="120" height="76" rx="12" fill="{t['panel']}" stroke="{t['key']}" stroke-width="2"/>
<text x="420" y="160" text-anchor="middle" class="big" fill="{t['key']}">f</text>
<text x="420" y="104" text-anchor="middle" class="lbl" fill="{t['muted']}">model</text>
<rect x="596" y="136" width="54" height="28" rx="6" fill="{t['panel']}" stroke="{t['accent']}" stroke-width="1.5"/>
<text x="623" y="155" text-anchor="middle" fill="{t['accent']}" font-weight="700">mat</text>
<text x="596" y="122" class="lbl" fill="{t['muted']}">output f(x)</text>
<circle r="4" fill="{t['accent']}"><animateMotion dur="1.6s" repeatCount="indefinite" path="M{in_end + 6} 150 H 352"/></circle>
<circle r="4" fill="{t['accent']}"><animateMotion dur="1.6s" begin="0.8s" repeatCount="indefinite" path="M488 150 H 586"/></circle>
"""


# ---------------------------------------------------------------- scene B: the network inside f
COLS = [(220, 3), (320, 5), (420, 6), (520, 5), (620, 2)]
B_TARGET = (520, 150)


def node_pos():
    out = []
    for x, n in COLS:
        out.append([(x, 150 + (j - (n - 1) / 2) * 34) for j in range(n)])
    return out


def scene_net(t):
    layers = node_pos()
    edges = []
    for a, b in zip(layers, layers[1:]):
        for p in a:
            for q in b:
                edges.append(f'<line x1="{p[0]}" y1="{p[1]:.1f}" x2="{q[0]}" y2="{q[1]:.1f}"/>')
    rnd = random.Random(7)
    pulses = []
    for k in range(5):
        pts = [rnd.choice(l) for l in layers]
        d = "M" + " L".join(f"{x} {y:.1f}" for x, y in pts)
        col = (t["accent"], t["key"], t["cool"])[k % 3]
        pulses.append(f'<path d="{d}" fill="none" stroke="{col}" stroke-width="2" opacity=".55" '
                      f'stroke-dasharray="40 600"><animate attributeName="stroke-dashoffset" from="40" to="-480" '
                      f'dur="2.2s" begin="{k * 0.45:.2f}s" repeatCount="indefinite"/></path>')
    nodes = []
    for li, l in enumerate(layers):
        for x, y in l:
            hi = (x, y) == (520, 150) or x == 520
            nodes.append(f'<circle cx="{x}" cy="{y:.1f}" r="9" fill="{t["panel"]}" '
                         f'stroke="{t["key"] if hi else t["muted"]}" stroke-width="{2 if hi else 1.4}"/>')
    top = 150 - 2 * 34 - 22
    return f"""
<g stroke="{t['muted']}" stroke-opacity=".22" stroke-width="1">{''.join(edges)}</g>
{''.join(pulses)}
<rect x="498" y="{top}" width="44" height="{2 * (150 - top)}" rx="10" fill="none" stroke="{t['key']}" stroke-dasharray="4 4" stroke-width="1.5"/>
<text x="520" y="{top - 8}" text-anchor="middle" class="lbl" fill="{t['key']}">layer ℓ</text>
{''.join(nodes)}
<text x="196" y="155" text-anchor="end" class="lbl" fill="{t['muted']}">x</text>
<text x="644" y="155" class="lbl" fill="{t['muted']}">f(x)</text>
"""


# ---------------------------------------------------------------- scene C: layer manifold
YAW, PITCH, DIST, FOC, CX, CY = math.radians(38), math.radians(30), 3.3, 340, 420, 140


def surf(u, v):
    return 0.42 * math.sin(2.1 * u) * math.cos(1.7 * v) + 0.22 * u * v


def proj(u, v, lift=0.0):
    X, Y, Z = u * 1.25, v * 1.25, surf(u, v) + lift
    xr = X * math.cos(YAW) - Y * math.sin(YAW)
    yr = X * math.sin(YAW) + Y * math.cos(YAW)
    depth = yr * math.cos(PITCH) - Z * math.sin(PITCH) + DIST
    up = yr * math.sin(PITCH) + Z * math.cos(PITCH)
    return CX + FOC * xr / depth, CY - FOC * up / depth, depth


def poly(pts):
    return "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y, _ in pts)


TRAJ = [(-0.85 + 1.45 * k / 40, -0.7 + 1.1 * math.sin(k / 40 * 2.4) * 0.8) for k in range(41)]
C_TARGET = tuple(round(c, 1) for c in proj(*TRAJ[-1])[:2])


def scene_manifold(t):
    n = 13
    lines = []
    for i in range(n):
        a = -1 + 2 * i / (n - 1)
        for pts in ([proj(a, -1 + 2 * k / 30) for k in range(31)],
                    [proj(-1 + 2 * k / 30, a) for k in range(31)]):
            mean_depth = sum(p[2] for p in pts) / len(pts)
            op = max(0.18, min(0.75, 1.15 - (mean_depth - 2.4) * 0.6))
            lines.append(f'<path d="{poly(pts)}" opacity="{op:.2f}"/>')
    # Point clusters sitting on the surface, gently drifting along it.
    rnd = random.Random(3)
    dots = []
    for col, (cu, cv) in ((t["accent"], (-0.5, 0.45)), (t["cool"], (0.45, 0.4)), (t["ok"], (0.05, -0.55))):
        for _ in range(11):
            u, v = cu + rnd.gauss(0, 0.13), cv + rnd.gauss(0, 0.13)
            du, dv = rnd.uniform(-0.12, 0.12), rnd.uniform(-0.12, 0.12)
            path = [proj(u + du * math.sin(k / 12 * math.tau), v + dv * math.cos(k / 12 * math.tau), 0.02) for k in range(13)]
            x0, y0, _ = path[0]
            rel = "M0 0 " + " ".join(f"L{x - x0:.1f} {y - y0:.1f}" for x, y, _ in path[1:])
            dots.append(f'<circle cx="{x0:.1f}" cy="{y0:.1f}" r="2.8" fill="{col}" opacity=".9">'
                        f'<animateMotion dur="{rnd.uniform(5, 8):.1f}s" repeatCount="indefinite" path="{rel}"/></circle>')
    traj = [proj(u, v, 0.03) for u, v in TRAJ]
    L = int(sum(math.dist(a[:2], b[:2]) for a, b in zip(traj, traj[1:]))) + 4
    tx, ty = C_TARGET
    return f"""
<g fill="none" stroke="{t['key']}" stroke-width="1">{''.join(lines)}</g>
{''.join(dots)}
<path d="{poly(traj)}" fill="none" stroke="{t['fg']}" stroke-width="2" stroke-linecap="round" stroke-dasharray="{L} {L}" stroke-dashoffset="{L}">
  <animate attributeName="stroke-dashoffset" values="{L};0;0" keyTimes="0;.6;1" dur="5s" repeatCount="indefinite"/>
</path>
<circle cx="{tx}" cy="{ty}" r="5" fill="{t['fg']}"/>
<circle cx="{tx}" cy="{ty}" r="5" fill="none" stroke="{t['fg']}" stroke-width="1.5">
  <animate attributeName="r" values="5;16" dur="1.4s" repeatCount="indefinite"/>
  <animate attributeName="opacity" values=".8;0" dur="1.4s" repeatCount="indefinite"/>
</circle>
<text x="{CX}" y="34" text-anchor="middle" class="lbl" fill="{t['key']}">activations at layer ℓ</text>
"""


CAPTIONS = [
    "a model maps an input to an output",
    "zoom in: the network that computed it",
    "zoom in: the shape one layer's activations live on",
]


def render(t):
    kf = [
        scene_keyframes("sA", 0, C_TARGET, A_TARGET),
        scene_keyframes("sB", 1, A_TARGET, B_TARGET),
        scene_keyframes("sC", 2, B_TARGET, C_TARGET),
    ] + [caption_keyframes(f"c{i}", i) for i in range(3)]
    caps = "".join(
        f'<text class="cap" style="animation-name:c{i}" x="{W / 2}" y="{H - 22}" text-anchor="middle" fill="{t["muted"]}">{c}</text>'
        for i, c in enumerate(CAPTIONS))
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="Animation: zooming from a model's input and output, into the neural network, into the activation manifold of one layer, and back to an input">
<style>
  text {{ font-family: ui-monospace, SFMono-Regular, 'JetBrains Mono', Menlo, Consolas, monospace; font-size: 15px; }}
  .lbl {{ font-size: 12px; letter-spacing: .04em; }}
  .big {{ font-family: Georgia, 'Times New Roman', serif; font-style: italic; font-size: 40px; }}
  .cap {{ font-size: 13px; opacity: 0; animation: {T}s linear infinite; }}
  .sc {{ transform-origin: 0 0; animation: {T}s linear infinite; }}
  #A {{ animation-name: sA; }} #B {{ animation-name: sB; opacity: 0; }} #C {{ animation-name: sC; opacity: 0; }}
  .cap:first-of-type {{ opacity: 1; }}
  {' '.join(kf)}
  @media (prefers-reduced-motion: reduce) {{ .sc, .cap {{ animation: none; }} }}
</style>
<clipPath id="card"><rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="12"/></clipPath>
<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="12" fill="{t['bg']}" stroke="{t['border']}"/>
<g clip-path="url(#card)">
  <g id="C" class="sc">{scene_manifold(t)}</g>
  <g id="B" class="sc">{scene_net(t)}</g>
  <g id="A" class="sc"><g transform="translate(420 150) scale(1.18) translate(-420 -150)">{scene_io(t)}</g></g>
</g>
{caps}
</svg>
"""


def main():
    os.makedirs(OUT, exist_ok=True)
    for name, theme in THEMES.items():
        with open(os.path.join(OUT, f"zoom-{name}.svg"), "w") as f:
            f.write(render(theme))
    print("target", C_TARGET)


if __name__ == "__main__":
    main()
