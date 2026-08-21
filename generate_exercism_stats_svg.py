#!/usr/bin/env python3
"""
generate_exercism_stats_svg.py

Generates a neon-themed "Exercism Stats" SVG card for a GitHub profile
README, in the same visual style as the existing LeetCode card
(https://leetcard.jacoblin.cool/...?colors=0a0014,1a0033,ffffff,c084fc,ff2d95,9b30ff,ffd93d,ffd93d)
and the repo's own generate_stats_svg.py output.

Two ways to get data in:

1. LIVE (best-effort scrape of the public profile page)
   python3 generate_exercism_stats_svg.py --user AurelieeF --live -o exercism_stats.svg

   Exercism does not expose a public, unauthenticated JSON API for profile
   stats (the old community scraper is archived, and the official API v2
   requires a personal access token). This mode scrapes the public HTML
   profile page instead, which is allowed to view but IS fragile: Exercism
   sits behind Cloudflare and the page markup can change at any time.
   If the scrape fails, it exits with an error instead of guessing.

2. MANUAL / CI-friendly (recommended)
   python3 generate_exercism_stats_svg.py \
       --user AurelieeF --display-name Aurelie \
       --reputation 5 --solutions 5 --badges 2 \
       --tracks Python \
       -o exercism_stats.svg

   Pass the numbers yourself (copy-pasted from your profile page, or piped
   in from another step). This is what's used to produce the first SVG
   below, and it's the safer choice for a scheduled GitHub Action since it
   never depends on scraping succeeding.

Embed the result in your README exactly like the other stats images:
    <img width="1000" src="./exercism_stats.svg" alt="Exercism Stats" />
"""

import argparse
import html
import re
import sys

# ---- Palette (matches the LeetCode card + Tech Stack badges) ----
BG_1 = "#0a0014"
BG_2 = "#1a0033"
TEXT = "#ffffff"
SUBTEXT = "#c084fc"
PINK = "#ff2d95"
PURPLE = "#9b30ff"
YELLOW = "#ffd93d"

ROW_COLORS = [PINK, PURPLE, YELLOW, PINK]


def esc(s):
    return html.escape(str(s), quote=True)


# Minimal 15x15 monoline icon paths (viewBox 0 0 24 24), one per secondary stat row.
ICON_STAR = "M12 2l2.6 6.6L21 9.2l-5 4.6 1.4 6.9L12 17.3 6.6 20.7 8 13.8 3 9.2l6.4-.6z"  # reputation
ICON_MEDAL = "M8.5 2h7l-1.8 5.4a6.5 6.5 0 1 1 -3.4 0z M12 12.4a3.1 3.1 0 1 0 0 6.2 3.1 3.1 0 0 0 0-6.2z"  # badges
ICON_LAYERS = "M12 3l9 4.5-9 4.5-9-4.5z M3 12l9 4.5 9-4.5 M3 16.5l9 4.5 9-4.5"  # tracks

ROW_ICONS = [ICON_STAR, ICON_MEDAL, ICON_LAYERS]
ROW_ACCENTS = [PINK, YELLOW, PURPLE]


def build_svg(display_name, username, reputation, solutions, badges, tracks):
    tracks_label = ", ".join(tracks) if tracks else "—"
    secondary = [
        ("Reputation", reputation),
        ("Badges collected", badges),
        ("Tracks", tracks_label),
    ]

    width, height = 520, 210
    pad = 28
    ring_cx, ring_cy, ring_r, ring_sw = 108, 108, 62, 9
    ring_circumference = 2 * 3.14159265 * ring_r

    right_x = 226
    right_w = width - pad - right_x

    divider_y = 90
    row_start_y = 118
    row_gap = 32

    rows_svg = []
    for i, (label, value) in enumerate(secondary):
        y = row_start_y + i * row_gap
        icon_path = ROW_ICONS[i % len(ROW_ICONS)]
        accent = ROW_ACCENTS[i % len(ROW_ACCENTS)]
        rows_svg.append(f'''
      <g transform="translate({right_x}, {y - 13})">
        <path d="{icon_path}" transform="scale(0.6)" fill="none" stroke="{accent}"
              stroke-width="2" stroke-linejoin="round" stroke-linecap="round" opacity="0.95" />
      </g>
      <text x="{right_x + 24}" y="{y}" class="stat-label">{esc(label)}</text>
      <text x="{width - pad}" y="{y}" class="stat-value" text-anchor="end">{esc(value)}</text>''')

    subtitle = f"@{username}" if username and username != display_name else ""
    hero_label = "solutions" if solutions != 1 else "solution"

    svg = f'''<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Exercism stats for {esc(display_name)}: {esc(solutions)} solutions published, {esc(reputation)} reputation, {esc(badges)} badges">
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
          transform="rotate(-90 {ring_cx} {ring_cy})">
    <animate attributeName="stroke-dasharray"
      values="0 {ring_circumference:.1f}; {ring_circumference * 0.86:.1f} {ring_circumference:.1f}"
      dur="1.1s" fill="freeze" />
  </circle>
  <text x="{ring_cx}" y="{ring_cy + 2}" text-anchor="middle" class="hero-value">{esc(solutions)}</text>
  <text x="{ring_cx}" y="{ring_cy + 24}" text-anchor="middle" class="hero-label">{hero_label.upper()}</text>

  <text x="{right_x}" y="42" class="card-title">Exercism Stats</text>
  <text x="{right_x}" y="62" class="card-subtitle">{esc(display_name)}{" &#183; " + esc(subtitle) if subtitle else ""}</text>
  <line x1="{right_x}" y1="{divider_y}" x2="{width - pad}" y2="{divider_y}" stroke="{SUBTEXT}" stroke-opacity="0.22" stroke-width="1" />
{"".join(rows_svg)}

  <text x="{pad}" y="{height - 16}" class="footer">exercism.org/profiles/{esc(username)}</text>
</svg>'''
    return svg


class ScrapeError(Exception):
    """Raised when the live profile page can't be fetched or parsed. Non-fatal by design:
    the caller decides whether to fail the build or just skip this run and keep the old SVG."""


def scrape_live(username):
    """Best-effort scrape of the public profile page. No auth, no guarantees."""
    try:
        import requests
    except ImportError:
        raise ScrapeError("`requests` is not installed. Run: pip install requests --break-system-packages")

    url = f"https://exercism.org/profiles/{username}"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
        )
    }
    try:
        resp = requests.get(url, headers=headers, timeout=15)
    except requests.RequestException as e:
        raise ScrapeError(f"Network error fetching {url}: {e}")

    if resp.status_code != 200:
        raise ScrapeError(
            f"Could not fetch {url} (HTTP {resp.status_code}). "
            "Exercism may be rate-limiting or Cloudflare-blocking this request."
        )
    page = resp.text

    def find_int(pattern, text, default=0):
        m = re.search(pattern, text)
        return int(m.group(1)) if m else default

    reputation = find_int(r'has\s*</span>\s*(\d+)\s*Reputation', page,
                           default=find_int(r'(\d+)\s*Reputation', page))
    solutions = find_int(r'(\d+)\s*solutions? published', page)
    badges = find_int(r'(\d+)\s*badges? collected', page)

    # The summary page above only lists the *most recent* solutions, so relying on it
    # alone for the track list would silently drop an older track once enough newer
    # solutions push it off that list. The dedicated /solutions page lists every
    # published solution (paginated), so walk it until a page comes back empty or
    # we hit a sane page cap, and union the tracks found across all pages.
    track_pattern = re.compile(r'/tracks/([a-z0-9\-]+)/exercises/[a-z0-9\-]+/solutions/' + re.escape(username))
    tracks_set = set(track_pattern.findall(page))

    for pg in range(1, 11):  # 10 pages is generous headroom; stop early once a page is empty
        sol_url = f"https://exercism.org/profiles/{username}/solutions?page={pg}"
        try:
            sol_resp = requests.get(sol_url, headers=headers, timeout=15)
        except requests.RequestException:
            break  # non-fatal: keep whatever tracks we already found
        if sol_resp.status_code != 200:
            break
        found = track_pattern.findall(sol_resp.text)
        if not found:
            break
        before = len(tracks_set)
        tracks_set.update(found)
        if len(tracks_set) == before and pg > 1:
            # no new tracks on this page and we're past page 1 — likely deep enough
            break

    tracks = sorted(t.replace("-", " ").title() for t in tracks_set)

    display_name_match = re.search(r'<title>([^<|]+)', page)
    display_name = display_name_match.group(1).strip() if display_name_match else username

    return {
        "display_name": display_name,
        "reputation": reputation,
        "solutions": solutions,
        "badges": badges,
        "tracks": tracks,
    }


def main():
    p = argparse.ArgumentParser(description="Generate a neon Exercism stats SVG card.")
    p.add_argument("--user", required=True, help="Exercism username, e.g. AurelieeF")
    p.add_argument("--display-name", default=None)
    p.add_argument("--live", action="store_true", help="Scrape exercism.org/profiles/<user> instead of using manual values")
    p.add_argument("--reputation", type=int, default=0)
    p.add_argument("--solutions", type=int, default=0)
    p.add_argument("--badges", type=int, default=0)
    p.add_argument("--tracks", nargs="*", default=[])
    p.add_argument("-o", "--output", default="exercism_stats.svg")
    p.add_argument(
        "--soft-fail",
        action="store_true",
        help="In --live mode, if scraping fails, print a warning and exit 0 without touching "
             "the output file (so a CI job doesn't hard-fail / doesn't commit a broken SVG).",
    )
    args = p.parse_args()

    if args.live:
        try:
            data = scrape_live(args.user)
        except ScrapeError as e:
            if args.soft_fail:
                print(f"::warning::Exercism scrape failed, keeping previous SVG. {e}", file=sys.stderr)
                return
            sys.exit(str(e))
        display_name = args.display_name or data["display_name"]
        reputation, solutions, badges, tracks = (
            data["reputation"], data["solutions"], data["badges"], data["tracks"]
        )
    else:
        display_name = args.display_name or args.user
        reputation, solutions, badges, tracks = (
            args.reputation, args.solutions, args.badges, args.tracks
        )

    svg = build_svg(display_name, args.user, reputation, solutions, badges, tracks)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
