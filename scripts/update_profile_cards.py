#!/usr/bin/env python3
"""Generate local SVG cards for the GitHub profile README.

This avoids depending on github-readme-stats.vercel.app, which can return 5xx
or rate-limit and leave broken images in the profile README.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any

USERNAME = os.getenv("GITHUB_PROFILE_USERNAME", "Thailee2710")
ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
API = "https://api.github.com"
FONT = "Inter, -apple-system, BlinkMacSystemFont, Segoe UI, Helvetica, Arial, sans-serif"

THEME = {
    "bg0": "#0D1117",
    "bg1": "#161B22",
    "surface": "#1B2430",
    "surface2": "#21262D",
    "border": "#30363D",
    "title": "#E6EDF3",
    "text": "#C9D1D9",
    "muted": "#8B949E",
    "accent": "#58A6FF",
    "accent2": "#BC8CFF",
    "success": "#3FB950",
    "warning": "#D29922",
    "danger": "#F85149",
}

LANG_COLORS = {
    "Python": "#3572A5",
    "Go": "#00ADD8",
    "HTML": "#E34C26",
    "JavaScript": "#F1E05A",
    "Shell": "#89E051",
    "Dockerfile": "#384D54",
    "CSS": "#563D7C",
    "TypeScript": "#3178C6",
    "Ruby": "#701516",
    "Java": "#B07219",
    "C": "#555555",
    "C++": "#F34B7D",
    "C#": "#178600",
    "PHP": "#4F5D95",
    "Rust": "#DEA584",
    "Kotlin": "#A97BFF",
    "Swift": "#F05138",
    "Vue": "#41B883",
    "Svelte": "#FF3E00",
    "SCSS": "#C6538C",
    "Jupyter Notebook": "#DA5B0B",
}


def github_token() -> str | None:
    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    return token.strip() if token else None


def api_get(path: str) -> Any:
    url = path if path.startswith("http") else API + path
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "thai-profile-card-generator",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = github_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "ignore")[:500]
        raise RuntimeError(f"GitHub API error {exc.code} for {url}: {detail}") from exc


def fetch_all_repos() -> list[dict[str, Any]]:
    repos: list[dict[str, Any]] = []
    page = 1
    while True:
        batch = api_get(f"/users/{USERNAME}/repos?per_page=100&page={page}&sort=updated&type=owner")
        if not batch:
            break
        repos.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return [r for r in repos if not r.get("fork")]


def fetch_languages(repos: list[dict[str, Any]]) -> Counter[str]:
    totals: Counter[str] = Counter()
    for repo in repos:
        langs_url = repo.get("languages_url")
        if not langs_url:
            continue
        try:
            data = api_get(langs_url)
        except Exception as exc:  # keep profile generation resilient
            print(f"warning: failed languages for {repo.get('full_name')}: {exc}", file=sys.stderr)
            continue
        for language, bytes_count in data.items():
            totals[language] += int(bytes_count)
    return totals


def svg_card(width: int, height: int, body: str, *, label: str) -> str:
    safe_label = escape(label)
    return f'''<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{safe_label}">
  <defs>
    <linearGradient id="cardBg" x1="0" y1="0" x2="{width}" y2="{height}" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="{THEME['bg0']}"/>
      <stop offset="1" stop-color="{THEME['bg1']}"/>
    </linearGradient>
    <linearGradient id="accentLine" x1="18" y1="0" x2="{width - 18}" y2="0" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="{THEME['accent']}"/>
      <stop offset="0.55" stop-color="{THEME['accent2']}"/>
      <stop offset="1" stop-color="{THEME['success']}"/>
    </linearGradient>
  </defs>
  <rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="16" fill="url(#cardBg)" stroke="{THEME['border']}"/>
  <rect x="18" y="14" width="{width - 36}" height="3" rx="1.5" fill="url(#accentLine)" opacity="0.95"/>
  {body}
</svg>
'''


def text(
    x: int,
    y: int,
    value: str,
    *,
    size: int = 14,
    color: str | None = None,
    weight: int = 400,
    anchor: str = "start",
    opacity: float = 1.0,
) -> str:
    return (
        f'<text x="{x}" y="{y}" fill="{color or THEME["text"]}" font-family="{FONT}" '
        f'font-size="{size}" font-weight="{weight}" text-anchor="{anchor}" opacity="{opacity}">{escape(value)}</text>'
    )


def compact_number(value: int) -> str:
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"{value / 1_000:.1f}K"
    return str(value)


def metric_box(x: int, y: int, w: int, h: int, label: str, value: str, color: str) -> str:
    return "\n  ".join(
        [
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="{THEME["surface"]}" stroke="{THEME["surface2"]}"/>',
            f'<circle cx="{x + 18}" cy="{y + 22}" r="5" fill="{color}"/>',
            text(x + 32, y + 26, label, size=11, color=THEME["muted"], weight=600),
            text(x + 16, y + 56, value, size=23, color=THEME["title"], weight=800),
        ]
    )


def stats_svg(repos: list[dict[str, Any]], langs: Counter[str]) -> str:
    total_stars = sum(int(r.get("stargazers_count", 0)) for r in repos)
    total_forks = sum(int(r.get("forks_count", 0)) for r in repos)
    updated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    top_lang = langs.most_common(1)[0][0] if langs else "N/A"

    body = "\n  ".join(
        [
            text(24, 44, USERNAME, size=20, color=THEME["title"], weight=800),
            text(24, 65, "GitHub profile overview", size=12, color=THEME["muted"], weight=500),
            text(340, 43, "Security Auditor", size=14, color=THEME["accent"], weight=800),
            text(340, 64, f"Top language: {top_lang}", size=12, color=THEME["text"], weight=500),
            metric_box(24, 82, 142, 72, "Repositories", compact_number(len(repos)), THEME["accent"]),
            metric_box(182, 82, 142, 72, "Stars", compact_number(total_stars), THEME["warning"]),
            metric_box(340, 82, 142, 72, "Forks", compact_number(total_forks), THEME["success"]),
            text(24, 168, f"Updated {updated}", size=10, color=THEME["muted"], weight=500),
        ]
    )
    return svg_card(520, 180, body, label=f"{USERNAME} GitHub profile stats")


def language_segments(top: list[tuple[str, int]], total: int, width: int) -> list[tuple[str, int, int]]:
    """Return rounded segment widths that exactly fill the stacked bar."""
    min_width = 3
    widths = [max(min_width, round(width * count / total)) for _lang, count in top]
    overflow = sum(widths) - width
    # If rounding/min-width made the bar too wide, shrink the widest segments first.
    while overflow > 0:
        adjustable = max(range(len(widths)), key=lambda i: widths[i])
        if widths[adjustable] <= min_width:
            break
        widths[adjustable] -= 1
        overflow -= 1
    # If rounding made the bar too short, add the remainder to the largest segment.
    if sum(widths) < width and widths:
        widths[max(range(len(widths)), key=lambda i: widths[i])] += width - sum(widths)
    return [(lang, count, segment_width) for (lang, count), segment_width in zip(top, widths)]


def languages_svg(langs: Counter[str]) -> str:
    total = sum(langs.values())
    top = langs.most_common(6)
    body: list[str] = [
        text(24, 44, "Most Used Languages", size=18, color=THEME["title"], weight=800),
        text(24, 64, "Repository language distribution", size=11, color=THEME["muted"], weight=500),
    ]

    if not total or not top:
        body.append(text(24, 112, "No language data available", size=13, color=THEME["muted"]))
        return svg_card(430, 180, "\n  ".join(body), label="Most used languages")

    bar_x, bar_y, bar_w, bar_h = 24, 82, 382, 12
    body.append(f'<rect x="{bar_x}" y="{bar_y}" width="{bar_w}" height="{bar_h}" rx="6" fill="{THEME["surface2"]}"/>')
    body.append('<clipPath id="langBarClip"><rect x="24" y="82" width="382" height="12" rx="6"/></clipPath>')
    cursor = bar_x
    for lang, _count, segment_width in language_segments(top, total, bar_w):
        color = LANG_COLORS.get(lang, THEME["accent2"])
        body.append(
            f'<rect x="{cursor}" y="{bar_y}" width="{segment_width}" height="{bar_h}" fill="{color}" clip-path="url(#langBarClip)"/>'
        )
        cursor += segment_width

    for i, (lang, count) in enumerate(top):
        pct = count / total * 100
        color = LANG_COLORS.get(lang, THEME["accent2"])
        col = i % 2
        row = i // 2
        x = 24 if col == 0 else 232
        pct_x = 190 if col == 0 else 398
        row_y = 121 + row * 24
        body.append(f'<circle cx="{x + 5}" cy="{row_y - 4}" r="4" fill="{color}"/>')
        body.append(text(x + 16, row_y, lang, size=13, color=THEME["text"], weight=650))
        body.append(text(pct_x, row_y, f"{pct:.1f}%", size=12, color=THEME["muted"], weight=600, anchor="end"))

    return svg_card(430, 180, "\n  ".join(body), label="Most used languages")


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    repos = fetch_all_repos()
    langs = fetch_languages(repos)
    (ASSETS / "stats.svg").write_text(stats_svg(repos, langs), encoding="utf-8")
    (ASSETS / "languages.svg").write_text(languages_svg(langs), encoding="utf-8")
    print(f"Generated cards for {USERNAME}: {len(repos)} repos, {len(langs)} languages")


if __name__ == "__main__":
    main()
