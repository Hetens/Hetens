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

    # Last-30-days sparkline as little bars under the avatar block.
    peak = max(s["last30"]) or 1
    spark = []
    for i, c in enumerate(s["last30"]):
        h = 3 + 37 * (c / peak)
        op = 0.25 if c == 0 else 0.45 + 0.55 * (c / peak)
        spark.append(
            f'<rect x="{36 + i * 7.4:.1f}" y="{278 - h:.1f}" width="5" height="{h:.1f}" rx="1.5" '
            f'fill="{t["ok"]}" opacity="{op:.2f}"/>'
        )

    # A tiny pixel-brain mascot, because mech interp.
    brain = [
        "...XXXXXXXX...",
        ".XXXoXXXXoXXX.",
        "XXXoXXXoXXXoXX",
        "XoXXXoXXXoXXXX",
        "XXoXXXoXXXXoXX",
        "XXXXoXXXoXXoXX",
        ".XXXXXXXXXXXX.",
        "...XXXXXXXo...",
        "........XX....",
        "........XX....",
    ]
    px = []
    for r, row in enumerate(brain):
        for c, ch in enumerate(row):
            if ch in "Xo":
                fill = t["key"] if ch == "o" else t["accent"]
                px.append(f'<rect x="{62 + c * 12}" y="{66 + r * 12}" width="11" height="11" rx="2" fill="{fill}"/>')

    today = dt.date.today().isoformat()
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="GitHub stats for {USER}">
<style>
  text {{ font-family: ui-monospace, SFMono-Regular, 'JetBrains Mono', Menlo, Consolas, monospace; font-size: 15px; }}
  .cur {{ animation: blink 1s steps(1) infinite; }}
  .bob {{ animation: bob 3s ease-in-out infinite; transform-origin: center; }}
  @keyframes blink {{ 50% {{ opacity: 0; }} }}
  @keyframes bob {{ 50% {{ transform: translateY(-4px); }} }}
  @media (prefers-reduced-motion: reduce) {{ .cur, .bob {{ animation: none; }} }}
</style>
<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="12" fill="{t['bg']}" stroke="{t['border']}"/>
<path d="M0.5 12.5a12 12 0 0 1 12-12h{W - 25}a12 12 0 0 1 12 12v24h-{W - 1}z" fill="{t['panel']}"/>
<line x1="0.5" y1="36.5" x2="{W - 0.5}" y2="36.5" stroke="{t['border']}"/>
<circle cx="22" cy="18.5" r="6" fill="#ff5f57"/><circle cx="42" cy="18.5" r="6" fill="#febc2e"/><circle cx="62" cy="18.5" r="6" fill="#28c840"/>
<text x="{W / 2}" y="23" text-anchor="middle" fill="{t['muted']}" font-size="13">hetens@umass: ~</text>
<g class="bob">{''.join(px)}</g>
<text x="36" y="214" fill="{t['muted']}" font-size="12">last 30 days</text>
{''.join(spark)}
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
