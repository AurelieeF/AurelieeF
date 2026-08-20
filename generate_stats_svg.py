"""
Generates a JARVIS-terminal-meets-Miami-vice styled SVG stats card from YOUR
live GitHub data, using the GitHub GraphQL API.

Palette: hot pink / purple / gold — no cyan this time, on purpose.

Setup:
  1. Create a Personal Access Token at github.com/settings/tokens
     - classic token, scope: read:user  (enough for public stats)
  2. Add it as a repo secret named STATS_PAT
  3. Set GH_USERNAME below (or pass as an env var).

Preview without hitting the API (uses fake sample numbers):
  python generate_stats_svg.py --preview

Real run:
  GH_TOKEN=ghp_xxx GH_USERNAME=yourname python generate_stats_svg.py
"""

import argparse
import math
import os
import sys
from datetime import date, datetime

import requests

USERNAME = os.environ.get("GH_USERNAME", "your-username")
TOKEN = os.environ.get("GH_TOKEN")
OUTPUT_FILE = "stats.svg"

PINK = "#ff2d95"
PURPLE = "#9b30ff"
GOLD = "#ffd93d"
BG_DARK = "#0a0014"
BG_PANEL = "#150022"
TRACK = "#2a0845"
TEXT_DIM = "#b892ff"

QUERY = """
query($login: String!) {
  user(login: $login) {
    followers { totalCount }
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays {
            date
            contributionCount
          }
        }
      }
    }
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false) {
      totalCount
      nodes {
        stargazerCount
      }
    }
  }
}
"""

MOCK_STATS = {
    "followers": {"totalCount": 7},
    "contributionsCollection": {
        "contributionCalendar": {
            "totalContributions": 312,
            "weeks": [],  # preview mode fakes the streak directly, see below
        }
    },
    "repositories": {
        "totalCount": 9,
        "nodes": [{"stargazerCount": n} for n in [2, 1, 0, 1, 0, 0, 0, 0, 0]],
    },
}


def fetch_stats():
    resp = requests.post(
        "https://api.github.com/graphql",
        json={"query": QUERY, "variables": {"login": USERNAME}},
        headers={"Authorization": f"bearer {TOKEN}"},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if "errors" in data:
        sys.exit(f"GitHub API error: {data['errors']}")
    if data["data"]["user"] is None:
        sys.exit(f"No GitHub user found for '{USERNAME}' — check GH_USERNAME.")
    return data["data"]["user"]


def current_streak(weeks):
    days = []
    for week in weeks:
        days.extend(week["contributionDays"])
    days.sort(key=lambda d: d["date"])

    today = str(date.today())
    streak = 0
    for day in reversed(days):
        if day["date"] == today and day["contributionCount"] == 0:
            continue
        if day["contributionCount"] > 0:
            streak += 1
        else:
            break
    return streak


def polar(cx, cy, r, angle_deg):
    a = math.radians(angle_deg - 90)  # 0deg = 12 o'clock
    return cx + r * math.cos(a), cy + r * math.sin(a)


def build_ticks(cx, cy, r_in, r_out, count=24):
    lines = []
    colors = [GOLD, PINK, PURPLE]
    for i in range(count):
        angle = i * (360 / count)
        x1, y1 = polar(cx, cy, r_in, angle)
        x2, y2 = polar(cx, cy, r_out, angle)
        color = colors[i % len(colors)] if i % 3 == 0 else PURPLE
        lines.append(
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'stroke="{color}" stroke-width="2" opacity="0.75"/>'
        )
    return "".join(lines)


def build_gauge(cx, cy, r, fraction, streak_label):
    circumference = 2 * math.pi * r
    filled = circumference * max(0.0, min(fraction, 1.0))
    gap = circumference - filled

    ticks = build_ticks(cx, cy, r + 14, r + 26)
    sweep_x, sweep_y = polar(cx, cy, r - 10, -35)

    return f'''
  <g>
    <circle cx="{cx}" cy="{cy}" r="{r + 40}" fill="none" stroke="{PURPLE}" stroke-width="1"
      stroke-dasharray="2,6" opacity="0.25"/>
    {ticks}
    <circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{TRACK}" stroke-width="14"/>
    <circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="url(#arcGrad)" stroke-width="14"
      stroke-linecap="round" stroke-dasharray="{filled:.1f} {gap:.1f}"
      transform="rotate(-90 {cx} {cy})" filter="url(#neonGlow)"/>
    <line x1="{cx}" y1="{cy}" x2="{sweep_x:.1f}" y2="{sweep_y:.1f}" stroke="{GOLD}"
      stroke-width="2" opacity="0.55" filter="url(#neonGlow)"/>
    <text x="{cx}" y="{cy - 6}" text-anchor="middle" font-family="Consolas, monospace"
      font-weight="bold" font-size="46" fill="#ffffff" filter="url(#neonGlow)">{streak_label}</text>
    <text x="{cx}" y="{cy + 26}" text-anchor="middle" font-family="Consolas, monospace"
      font-size="13" letter-spacing="3" fill="{GOLD}">DAY STREAK</text>
    <text x="{cx}" y="{cy - r - 46}" text-anchor="middle" font-family="Consolas, monospace"
      font-size="12" letter-spacing="2" fill="{TEXT_DIM}">ACTIVITY_LEVEL: {fraction * 100:.0f}%</text>
  </g>'''


def build_readout_rows(rows, x_label, x_value, start_y, gap):
    out = []
    for i, (label, value) in enumerate(rows):
        y = start_y + i * gap
        out.append(f'''
    <text x="{x_label}" y="{y}" font-family="Consolas, monospace" font-size="14" fill="{GOLD}"
      letter-spacing="1">{label}</text>
    <text x="{x_value}" y="{y}" font-family="Consolas, monospace" font-size="15" fill="#ffffff"
      text-anchor="end" filter="url(#neonGlow)">{value}</text>
    <line x1="{x_label}" y1="{y + 12}" x2="{x_value}" y2="{y + 12}" stroke="{PINK}"
      stroke-width="1" opacity="0.3" stroke-dasharray="3,3"/>''')
    return "".join(out)


def build_svg(stats, username, preview_streak=None, preview_fraction=None):
    cal = stats["contributionsCollection"]["contributionCalendar"]
    contributions = cal["totalContributions"]
    streak = preview_streak if preview_streak is not None else current_streak(cal["weeks"])
    fraction = preview_fraction if preview_fraction is not None else min(contributions / 365, 1.0)
    repos = stats["repositories"]["totalCount"]
    stars = sum(r["stargazerCount"] for r in stats["repositories"]["nodes"])
    followers = stats["followers"]["totalCount"]

    rows = [
        ("CONTRIBUTIONS_1Y", f"{contributions:,}"),
        ("PUBLIC_REPOS", f"{repos}"),
        ("TOTAL_STARS", f"{stars}"),
        ("FOLLOWERS", f"{followers}"),
    ]
    readout = build_readout_rows(rows, x_label=520, x_value=850, start_y=170, gap=46)
    gauge = build_gauge(cx=240, cy=300, r=130, fraction=fraction, streak_label=str(streak))

    today_str = datetime.utcnow().strftime("%Y-%m-%d")

    return f'''<svg width="900" height="520" viewBox="0 0 900 520" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="bgGrad" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="{BG_DARK}"/>
      <stop offset="100%" stop-color="#1a0033"/>
    </linearGradient>
    <linearGradient id="arcGrad" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="{PINK}"/>
      <stop offset="50%" stop-color="{PURPLE}"/>
      <stop offset="100%" stop-color="{GOLD}"/>
    </linearGradient>
    <filter id="neonGlow" x="-50%" y="-50%" width="200%" height="200%">
      <feGaussianBlur stdDeviation="3" result="blur"/>
      <feMerge>
        <feMergeNode in="blur"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>
    <pattern id="scanlines" width="4" height="4" patternUnits="userSpaceOnUse">
      <rect width="4" height="2" fill="#000000" opacity="0.10"/>
    </pattern>
  </defs>

  <rect width="900" height="520" rx="16" fill="url(#bgGrad)"/>
  <rect width="900" height="520" rx="16" fill="url(#scanlines)"/>
  <rect x="2" y="2" width="896" height="516" rx="16" fill="none" stroke="{PURPLE}" stroke-width="2" opacity="0.6"/>

  <!-- terminal title bar -->
  <rect x="0" y="0" width="900" height="44" rx="16" fill="{BG_PANEL}"/>
  <rect x="0" y="28" width="900" height="16" fill="{BG_PANEL}"/>
  <circle cx="24" cy="22" r="7" fill="{PINK}"/>
  <circle cx="48" cy="22" r="7" fill="{PURPLE}"/>
  <circle cx="72" cy="22" r="7" fill="{GOLD}"/>
  <text x="100" y="27" font-family="Consolas, monospace" font-size="14" fill="#d9c8ff">user@{username}:~$ ./github_stats.sh</text>

  <!-- HUD corners -->
  <path d="M20,74 L20,44 L50,44" stroke="{GOLD}" stroke-width="3" fill="none"/>
  <path d="M850,44 L880,44 L880,74" stroke="{GOLD}" stroke-width="3" fill="none"/>
  <path d="M20,476 L20,500 L50,500" stroke="{PINK}" stroke-width="3" fill="none"/>
  <path d="M850,500 L880,500 L880,476" stroke="{PINK}" stroke-width="3" fill="none"/>

  {gauge}

  <text x="520" y="130" font-family="Consolas, monospace" font-size="15" fill="{PURPLE}">&gt; querying github.com/{username} ...</text>
{readout}

  <text x="30" y="500" font-family="Consolas, monospace" font-size="12" fill="{TEXT_DIM}">&gt; SYSTEM STATUS: ONLINE_</text>
  <text x="870" y="500" font-family="Consolas, monospace" font-size="12" fill="{TEXT_DIM}" text-anchor="end">LAST SYNC: {today_str}</text>
</svg>'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--preview", action="store_true", help="Render with fake sample data, no API calls")
    args = parser.parse_args()

    if args.preview:
        svg = build_svg(MOCK_STATS, username="your_username", preview_streak=14, preview_fraction=0.84)
    else:
        if not TOKEN:
            sys.exit("Set the GH_TOKEN environment variable to a GitHub personal access token first.")
        stats = fetch_stats()
        svg = build_svg(stats, username=USERNAME)

    with open(OUTPUT_FILE, "w") as f:
        f.write(svg)
    print(f"Wrote {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
