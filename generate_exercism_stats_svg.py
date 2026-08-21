#!/usr/bin/env python3
"""
generate_exercism_stats_svg.py

Generates a neon-themed "Exercism Stats" SVG card for a GitHub profile
README, styled to match the existing LeetCode card
(https://leetcard.jacoblin.cool/...?colors=0a0014,1a0033,ffffff,c084fc,ff2d95,9b30ff,ffd93d,ffd93d).

Data source: NOT exercism.org. That site sits behind Cloudflare and blocks
automated requests (including from GitHub Actions) — confirmed by hand,
every route tried came back 403 with a Cloudflare challenge page, token or
not. Instead, this reads the GitHub repo that Exercism's own "GitHub
Syncer" feature already pushes your solutions into
(github.com/AurelieeF/exercism-solutions), via GitHub's own API. That's
GitHub talking to GitHub — no Cloudflare in the way, no token needed for a
public repo, and it's exactly the data you actually wanted: how many
exercises you've done, per track, straight from the folders the Syncer
creates (solutions/<track>/<exercise-slug>/).

Trade-off: this can't show Reputation or Badges — those only exist on
exercism.org's site, not in the repo. What it shows instead: total
exercises completed, broken down by track. That's a fair swap given the
goal was "how many Python exercises did I do," not the exercism.org
gamification numbers.

Usage:
  python3 generate_exercism_stats_svg.py \
      --user AurelieeF --display-name Aurelie \
      --repo AurelieeF/exercism-solutions --repo-path solutions \
      -o exercism_stats.svg

Embed the result in your README exactly like the other stats images:
    <img width="1000" src="./exercism_stats.svg" alt="Exercism Stats" />
"""

import argparse
import html
import os
import sys

# ---- Palette (matches the LeetCode card + Tech Stack badges) ----
BG_1 = "#0a0014"
BG_2 = "#1a0033"
TEXT = "#ffffff"
SUBTEXT = "#c084fc"
PINK = "#ff2d95"
PURPLE = "#9b30ff"
YELLOW = "#ffd93d"

ROW_ACCENTS = [PINK, PURPLE, YELLOW]

# Minimal monoline "code brackets" icon (viewBox 0 0 24 24), reused per track row.
ICON_TRACK = "M8 4L2 12l6 8 M16 4l6 8-6 8 M13 3l-2 18"


def esc(s):
    return html.escape(str(s), quote=True)


class FetchError(Exception):
    """Raised when the sync repo can't be read. Non-fatal by design: the caller
    decides whether to fail the build or just skip this run and keep the old SVG."""


def fetch_from_solutions_repo(repo, base_path="solutions", branch="main"):
    """Reads the exercise folder structure straight from a GitHub repo via the
    GitHub REST API (git trees, recursive) — no auth needed for a public repo.
    Expects paths shaped like '<base_path>/<track>/<exercise-slug>/...',
    exactly what Exercism's GitHub Syncer produces.
    """
    try:
        import requests
    except ImportError:
        raise FetchError("`requests` is not installed. Run: pip install requests --break-system-packages")

    url = f"https://api.github.com/repos/{repo}/git/trees/{branch}?recursive=1"
    headers = {"Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        # Optional: raises the API rate limit from 60/hr to 5000/hr. In a GitHub
        # Action, the default GITHUB_TOKEN can be passed in for this — it does NOT
        # need write access to the sync repo, reading a public repo works with any
        # valid token or none at all.
        headers["Authorization"] = f"Bearer {token}"

    try:
        resp = requests.get(url, headers=headers, timeout=20)
    except requests.RequestException as e:
        raise FetchError(f"Network error fetching {url}: {e}")

    if resp.status_code != 200:
        raise FetchError(
            f"Could not read {repo}@{branch} (HTTP {resp.status_code}): {resp.text[:200]}"
        )

    data = resp.json()
    if data.get("truncated"):
        raise FetchError(
            f"GitHub's tree response for {repo}@{branch} was truncated (repo too large "
            "for a single call) — counts would be incomplete, refusing to guess."
        )

    prefix = base_path.strip("/") + "/"
    track_exercises = {}  # track -> set of exercise slugs

    for entry in data.get("tree", []):
        if entry.get("type") != "tree":
            continue
        path = entry.get("path", "")
        if not path.startswith(prefix):
            continue
        parts = path[len(prefix):].split("/")
        if len(parts) == 2 and all(parts):
            track, exercise = parts
            track_exercises.setdefault(track, set()).add(exercise)

    if not track_exercises:
        raise FetchError(
            f"No '{base_path}/<track>/<exercise>' folders found in {repo}@{branch} — "
            "check --repo-path matches the real folder structure."
        )

    tracks = sorted(track_exercises.keys())
    counts = [(t.replace("-", " ").title(), len(track_exercises[t])) for t in tracks]
    total = sum(c for _, c in counts)
    return {"total": total, "track_counts": counts}


def build_svg(display_name, username, total, track_counts, repo):
    width, height_min = 520, 210
    pad = 28
    ring_cx, ring_cy, ring_r, ring_sw = 108, 108, 62, 9
    ring_circumference = 2 * 3.14159265 * ring_r

    right_x = 226
    divider_y = 90
    row_start_y = 118
    row_gap = 32

    # Card grows to fit however many tracks there are (min 3 rows worth of height).
    n_rows = max(len(track_counts), 3)
    height = max(height_min, row_start_y + n_rows * row_gap + 34)

    rows_svg = []
    if track_counts:
        for i, (track, count) in enumerate(track_counts):
            y = row_start_y + i * row_gap
            accent = ROW_ACCENTS[i % len(ROW_ACCENTS)]
            rows_svg.append(f'''
      <g transform="translate({right_x}, {y - 13})">
        <path d="{ICON_TRACK}" transform="scale(0.55)" fill="none" stroke="{accent}"
              stroke-width="2.4" stroke-linejoin="round" stroke-linecap="round" opacity="0.95" />
      </g>
      <text x="{right_x + 24}" y="{y}" class="stat-label">{esc(track)}</text>
      <text x="{width - pad}" y="{y}" class="stat-value" text-anchor="end">{esc(count)}</text>''')
    else:
        rows_svg.append(f'''
      <text x="{right_x}" y="{row_start_y}" class="stat-label" opacity="0.7">No exercises found yet</text>''')

    subtitle = f"@{username}" if username and username != display_name else ""
    hero_label = "exercises" if total != 1 else "exercise"

    svg = f'''<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Exercism stats for {esc(display_name)}: {esc(total)} exercises completed across {esc(len(track_counts))} track(s)">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="{BG_1}" />
      <stop offset="100%" stop-color="{BG_2}" />
    </linearGradient>
    <linearGradient id="titleGrad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="{PINK}" />
      <stop offset="50%" stop-color="{PURPLE}" />
      <stop offset="100%" stop-color="{YELLOW}" />
    </linearGradient>
    <linearGradient id="ringGrad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="{PINK}" />
      <stop offset="50%" stop-color="{PURPLE}" />
      <stop offset="100%" stop-color="{YELLOW}" />
    </linearGradient>
    <radialGradient id="glow" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="{PURPLE}" stop-opacity="0.35" />
      <stop offset="100%" stop-color="{PURPLE}" stop-opacity="0" />
    </radialGradient>
    <style>
      .card-title    {{ font: 700 21px 'Segoe UI', Ubuntu, Sans-Serif; fill: url(#titleGrad); }}
      .card-subtitle {{ font: 400 12px 'Segoe UI', Ubuntu, Sans-Serif; fill: {SUBTEXT}; }}
      .stat-label    {{ font: 400 13.5px 'Segoe UI', Ubuntu, Sans-Serif; fill: {TEXT}; opacity: 0.92; }}
      .stat-value    {{ font: 700 15px 'Segoe UI', Ubuntu, Sans-Serif; fill: {TEXT}; }}
      .hero-value    {{ font: 700 42px 'Segoe UI', Ubuntu, Sans-Serif; fill: {TEXT}; }}
      .hero-label    {{ font: 600 12px 'Segoe UI', Ubuntu, Sans-Serif; fill: {SUBTEXT}; letter-spacing: 0.05em; }}
      .footer        {{ font: 400 10.5px 'Segoe UI', Ubuntu, Sans-Serif; fill: {SUBTEXT}; opacity: 0.8; }}
    </style>
  </defs>

  <rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="18"
        fill="url(#bg)" stroke="{PURPLE}" stroke-opacity="0.5" />

  <circle cx="{ring_cx}" cy="{ring_cy}" r="{ring_r + 34}" fill="url(#glow)" />

  <!-- decorative ring framing the headline number (ornamental, not a % gauge) -->
  <circle cx="{ring_cx}" cy="{ring_cy}" r="{ring_r}" fill="none"
          stroke="{BG_2}" stroke-width="{ring_sw}" opacity="0.6" />
  <circle cx="{ring_cx}" cy="{ring_cy}" r="{ring_r}" fill="none"
          stroke="url(#ringGrad)" stroke-width="{ring_sw}" stroke-linecap="round"
          stroke-dasharray="{ring_circumference * 0.86:.1f} {ring_circumference:.1f}"
          transform="rotate(-90 {ring_cx} {ring_cy})" />
  <text x="{ring_cx}" y="{ring_cy + 2}" text-anchor="middle" class="hero-value">{esc(total)}</text>
  <text x="{ring_cx}" y="{ring_cy + 24}" text-anchor="middle" class="hero-label">{hero_label.upper()}</text>

  <text x="{right_x}" y="42" class="card-title">Exercism Stats</text>
  <text x="{right_x}" y="62" class="card-subtitle">{esc(display_name)}{" &#183; " + esc(subtitle) if subtitle else ""}</text>
  <line x1="{right_x}" y1="{divider_y}" x2="{width - pad}" y2="{divider_y}" stroke="{SUBTEXT}" stroke-opacity="0.22" stroke-width="1" />
{"".join(rows_svg)}

  <text x="{pad}" y="{height - 16}" class="footer">github.com/{esc(repo)}</text>
</svg>'''
    return svg


def main():
    p = argparse.ArgumentParser(description="Generate a neon Exercism stats SVG card from your GitHub sync repo.")
    p.add_argument("--user", required=True, help="Display name / Exercism username, e.g. AurelieeF")
    p.add_argument("--display-name", default=None)
    p.add_argument("--repo", required=True, help="owner/repo where Exercism's GitHub Syncer pushes solutions, e.g. AurelieeF/exercism-solutions")
    p.add_argument("--repo-path", default="solutions", help="Path inside the repo containing <track>/<exercise> folders (default: solutions)")
    p.add_argument("--branch", default="main")
    p.add_argument("-o", "--output", default="exercism_stats.svg")
    p.add_argument(
        "--soft-fail",
        action="store_true",
        help="If the repo can't be read, print a warning and exit 0 without touching "
             "the output file (so a CI job doesn't hard-fail / doesn't commit a broken SVG).",
    )
    args = p.parse_args()

    try:
        data = fetch_from_solutions_repo(args.repo, base_path=args.repo_path, branch=args.branch)
    except FetchError as e:
        if args.soft_fail:
            print(f"::warning::Could not read {args.repo}, keeping previous SVG. {e}", file=sys.stderr)
            return
        sys.exit(str(e))

    display_name = args.display_name or args.user
    svg = build_svg(display_name, args.user, data["total"], data["track_counts"], args.repo)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"Wrote {args.output} — {data['total']} exercises across {len(data['track_counts'])} track(s)")


if __name__ == "__main__":
    main()
