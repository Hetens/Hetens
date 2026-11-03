#!/usr/bin/env python3
"""Render a neofetch-style GitHub stats card (dark + light) as self-hosted SVGs.

No third-party card service: queries the GitHub GraphQL API with GITHUB_TOKEN
and writes assets/stats-dark.svg and assets/stats-light.svg.
"""
import datetime as dt
import html
import json
import os
import urllib.request
from collections import Counter

USER = os.environ.get("GH_USER", "Hetens")
TOKEN = os.environ["GITHUB_TOKEN"]
OUT = os.path.join(os.path.dirname(__file__), "..", "assets")

QUERY = """
query($login: String!) {
  user(login: $login) {
    followers { totalCount }
    contributionsCollection {
      totalCommitContributions
      totalPullRequestContributions
      totalIssueContributions
      restrictedContributionsCount
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC) {
      totalCount
      nodes {
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
  }
}
"""

# Notebooks/markup inflate byte counts without saying much about what you write.
SKIP_LANGS = {"Jupyter Notebook", "HTML", "CSS", "TeX", "Makefile", "Dockerfile", "Shell"}


def fetch():
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": USER}}).encode(),
        headers={"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as r:
        body = json.load(r)
    if "errors" in body:
        raise SystemExit(body["errors"])
    return body["data"]["user"]


def streaks(days):
    days = sorted(days, key=lambda d: d["date"])
    longest = run = 0
    for d in days:
        run = run + 1 if d["contributionCount"] else 0
        longest = max(longest, run)
    current = 0
    # Today not having a contribution yet shouldn't break the streak.
    for i, d in enumerate(reversed(days)):
        if d["contributionCount"]:
            current += 1
        elif i == 0:
            continue
        else:
            break
    return current, longest


def collect(u):
    cc = u["contributionsCollection"]
    days = [d for w in cc["contributionCalendar"]["weeks"] for d in w["contributionDays"]]
    cur, longest = streaks(days)
    langs, colors = Counter(), {}
    for repo in u["repositories"]["nodes"]:
        for e in repo["languages"]["edges"]:
            name = e["node"]["name"]
            if name in SKIP_LANGS:
                continue
            langs[name] += e["size"]
            colors[name] = e["node"]["color"] or "#888"
    total = sum(langs.values()) or 1
    top = [(n, s / total, colors[n]) for n, s in langs.most_common(5) if s / total >= 0.01]
    return {
        "contribs": cc["contributionCalendar"]["totalContributions"],
        "commits": cc["totalCommitContributions"],
        "private": cc["restrictedContributionsCount"],
        "prs": cc["totalPullRequestContributions"],
        "issues": cc["totalIssueContributions"],
        "stars": sum(r["stargazerCount"] for r in u["repositories"]["nodes"]),
        "repos": u["repositories"]["totalCount"],
        "followers": u["followers"]["totalCount"],
        "streak": cur,
        "longest": longest,
        "last30": [d["contributionCount"] for d in sorted(days, key=lambda d: d["date"])[-30:]],
        "langs": top,
    }


def draw_handheld(last30, t, x0=70, y0=46):
    """A little pocket console whose LCD shows the last 30 days of contributions."""
    body, edge, ink = "#d6d2c8", "#b8b4aa", "#2b2b2b"
    lcd, lcd_ink, lcd_dim = "#9bbc0f", "#0f380f", "#306230"
    w, h, r, rbr = 156, 258, 10, 38
    outline = (f"M{x0 + r} {y0} H{x0 + w - r} a{r} {r} 0 0 1 {r} {r} V{y0 + h - rbr} "
               f"a{rbr} {rbr} 0 0 1 -{rbr} {rbr} H{x0 + r} a{r} {r} 0 0 1 -{r} -{r} V{y0 + r} a{r} {r} 0 0 1 {r} -{r}z")
    bz_x, bz_y, bz_w, bz_h = x0 + 12, y0 + 14, w - 24, 108
    bezel = (f"M{bz_x + 6} {bz_y} H{bz_x + bz_w - 6} a6 6 0 0 1 6 6 V{bz_y + bz_h - 22} "
             f"a22 22 0 0 1 -22 22 H{bz_x + 6} a6 6 0 0 1 -6 -6 V{bz_y + 6} a6 6 0 0 1 6 -6z")
    sx, sy, sw, sh = x0 + 32, y0 + 26, 100, 80
    peak = max(last30) or 1
    bars = []
    for i, c in enumerate(last30):
        bh = 2 + 44 * (c / peak) ** 0.5
        bars.append(f'<rect x="{sx + 5 + i * 3.0:.1f}" y="{sy + sh - 10 - bh:.1f}" width="2.2" height="{bh:.1f}" '
                    f'fill="{lcd_ink if c else lcd_dim}"/>')
    cx, cy = x0 + 38, y0 + 176
    grille = "".join(
        f'<line x1="{x0 + 98 + i * 9}" y1="{y0 + 246}" x2="{x0 + 112 + i * 9}" y2="{y0 + 222}" stroke="{edge}" stroke-width="3" stroke-linecap="round"/>'
        for i in range(5))
    return f"""<g>
<path d="{outline}" fill="{body}" stroke="{edge}" stroke-width="1.5"/>
<path d="{bezel}" fill="#55566a"/>
<circle class="led" cx="{bz_x + 10}" cy="{bz_y + 46}" r="3" fill="#ff4d4d"/>
<rect x="{sx}" y="{sy}" width="{sw}" height="{sh}" rx="2" fill="{lcd}"/>
<text x="{sx + 5}" y="{sy + 13}" fill="{lcd_dim}" font-size="7" letter-spacing=".5">30 DAYS</text>
{''.join(bars)}
<line x1="{sx + 4}" y1="{sy + sh - 9.5}" x2="{sx + sw - 4}" y2="{sy + sh - 9.5}" stroke="{lcd_dim}" stroke-width="1"/>
<text x="{bz_x + 2}" y="{y0 + 140}" fill="#2e3a87" font-size="12" font-weight="700" font-style="italic">Hetens</text>
<rect x="{cx - 17}" y="{cy - 6}" width="34" height="12" rx="2" fill="{ink}"/>
<rect x="{cx - 6}" y="{cy - 17}" width="12" height="34" rx="2" fill="{ink}"/>
<circle cx="{x0 + 104}" cy="{y0 + 184}" r="10.5" fill="#8b1e4f"/>
<circle cx="{x0 + 130}" cy="{y0 + 170}" r="10.5" fill="#8b1e4f"/>
<rect x="{x0 + 42}" y="{y0 + 218}" width="22" height="7" rx="3.5" fill="#8a877f" transform="rotate(-25 {x0 + 53} {y0 + 221})"/>
<rect x="{x0 + 72}" y="{y0 + 218}" width="22" height="7" rx="3.5" fill="#8a877f" transform="rotate(-25 {x0 + 83} {y0 + 221})"/>
{grille}
</g>"""


THEMES = {
    "dark": dict(bg="#0d1117", panel="#161b22", border="#30363d", fg="#e6edf3",
                 muted="#8b949e", key="#c084fc", accent="#f472b6", ok="#4ade80"),
    "light": dict(bg="#ffffff", panel="#f6f8fa", border="#d0d7de", fg="#1f2328",
                  muted="#59636e", key="#7c3aed", accent="#db2777", ok="#16a34a"),
}


def render(s, t):
    W, H = 840, 316
    e = html.escape
    rows = [
        ("contributions", f"{s['contribs']:,} in the last year"),
        ("commits", f"{s['commits']:,} public + {s['private']:,} private contribs"),
        ("pull requests", f"{s['prs']:,}"),
        ("stars earned", f"{s['stars']:,} across {s['repos']} public repos"),
        ("streak", f"{s['streak']} day{'s' if s['streak'] != 1 else ''} 🔥  (best: {s['longest']})"),
    ]
    lines = []
    y = 104
    for i, (k, v) in enumerate(rows):
        lines.append(
            f'<text x="300" y="{y}">'
            f'<tspan fill="{t["key"]}" font-weight="700">{e(k)}</tspan>'
            f'<tspan fill="{t["muted"]}">: </tspan><tspan fill="{t["fg"]}">{e(v)}</tspan></text>'
        )
        y += 24

    # Language bar + legend.
    bar_x, bar_w, bar_y = 300, 510, 250
    segs, x = [], bar_x
    for n, frac, c in s["langs"]:
        w = max(frac * bar_w, 2)
        segs.append(f'<rect x="{x:.1f}" y="{bar_y}" width="{w:.1f}" height="8" fill="{c}"/>')
        x += w
    legend, lx = [], bar_x
    for n, frac, c in s["langs"]:
        label = f"{n} {frac * 100:.0f}%"
        legend.append(
            f'<circle cx="{lx + 4}" cy="{bar_y + 26}" r="4" fill="{c}"/>'
            f'<text x="{lx + 13}" y="{bar_y + 30}" fill="{t["muted"]}" font-size="12">{e(label)}</text>'
        )
        lx += 13 + len(label) * 8.6 + 18

    handheld = draw_handheld(s["last30"], t)

    today = dt.date.today().isoformat()
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="GitHub stats for {USER}">
<style>
  text {{ font-family: ui-monospace, SFMono-Regular, 'JetBrains Mono', Menlo, Consolas, monospace; font-size: 15px; }}
  .cur {{ animation: blink 1s steps(1) infinite; }}
  .led {{ animation: led 2.4s ease-in-out infinite; }}
  @keyframes blink {{ 50% {{ opacity: 0; }} }}
  @keyframes led {{ 50% {{ opacity: .35; }} }}
  @media (prefers-reduced-motion: reduce) {{ .cur, .led {{ animation: none; }} }}
</style>
<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="12" fill="{t['bg']}" stroke="{t['border']}"/>
<path d="M0.5 12.5a12 12 0 0 1 12-12h{W - 25}a12 12 0 0 1 12 12v24h-{W - 1}z" fill="{t['panel']}"/>
<line x1="0.5" y1="36.5" x2="{W - 0.5}" y2="36.5" stroke="{t['border']}"/>
<circle cx="22" cy="18.5" r="6" fill="#ff5f57"/><circle cx="42" cy="18.5" r="6" fill="#febc2e"/><circle cx="62" cy="18.5" r="6" fill="#28c840"/>
<text x="{W / 2}" y="23" text-anchor="middle" fill="{t['muted']}" font-size="13">hetens@umass: ~</text>
{handheld}
<text x="300" y="70" fill="{t['ok']}" font-weight="700">➜ <tspan fill="{t['fg']}" font-weight="400">neofetch --github</tspan><tspan class="cur" fill="{t['fg']}"> ▌</tspan></text>
{''.join(lines)}
<text x="{bar_x}" y="{bar_y - 10}" fill="{t['muted']}" font-size="12">languages (by bytes, public repos)</text>
<clipPath id="bar"><rect x="{bar_x}" y="{bar_y}" width="{bar_w}" height="8" rx="4"/></clipPath>
<g clip-path="url(#bar)">{''.join(segs)}</g>
{''.join(legend)}
<text x="{W - 16}" y="{H - 10}" text-anchor="end" fill="{t['muted']}" font-size="10" opacity="0.7">updated {today}</text>
</svg>
"""


def main():
    s = collect(fetch())
    os.makedirs(OUT, exist_ok=True)
    for name, theme in THEMES.items():
        with open(os.path.join(OUT, f"stats-{name}.svg"), "w") as f:
            f.write(render(s, theme))
    print(json.dumps({k: v for k, v in s.items() if k != "last30"}, indent=2))


if __name__ == "__main__":
    main()
