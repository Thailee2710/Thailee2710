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

THEME = {
    "bg": "#282a36",
    "border": "#44475a",
    "title": "#ff79c6",
    "text": "#f8f8f2",
    "muted": "#bd93f9",
    "accent": "#50fa7b",
    "orange": "#ffb86c",
    "cyan": "#8be9fd",
    "red": "#ff5555",
}

LANG_COLORS = {
    "Python": "#3572A5",
    "Go": "#00ADD8",
    "HTML": "#e34c26",
    "JavaScript": "#f1e05a",
    "Shell": "#89e051",
    "Dockerfile": "#384d54",
    "CSS": "#563d7c",
    "TypeScript": "#3178c6",
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


def svg_card(width: int, height: int, body: str) -> str:
    return f'''<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="GitHub profile stats">
  <rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="10" fill="{THEME['bg']}" stroke="{THEME['border']}"/>
  {body}
</svg>
'''


def text(x: int, y: int, value: str, *, size: int = 14, color: str | None = None, weight: int = 400) -> str:
    return f'<text x="{x}" y="{y}" fill="{color or THEME["text"]}" font-family="Segoe UI, Ubuntu, Arial, sans-serif" font-size="{size}" font-weight="{weight}">{escape(value)}</text>'


def stats_svg(repos: list[dict[str, Any]], langs: Counter[str]) -> str:
    total_stars = sum(int(r.get("stargazers_count", 0)) for r in repos)
    total_forks = sum(int(r.get("forks_count", 0)) for r in repos)
    updated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    top_lang = langs.most_common(1)[0][0] if langs else "N/A"
    body = "\n  ".join(
        [
            text(20, 34, f"{USERNAME}'s GitHub Stats", size=18, color=THEME["title"], weight=700),
            text(22, 70, f"📦 Public repos: {len(repos)}", size=14),
            text(22, 100, f"⭐ Stars earned: {total_stars}", size=14),
            text(22, 130, f"⑂ Forks: {total_forks}", size=14),
            text(210, 70, f"💻 Top language: {top_lang}", size=14),
            text(210, 100, "🛡 Security Auditor", size=14, color=THEME["accent"], weight=600),
            text(210, 130, "⚡ FastAPI · Docker · Git", size=14, color=THEME["cyan"]),
            text(22, 162, f"Updated: {updated}", size=11, color=THEME["muted"]),
        ]
    )
    return svg_card(520, 180, body)


def languages_svg(langs: Counter[str]) -> str:
    total = sum(langs.values()) or 1
    top = langs.most_common(6)
    x = 20
    y = 68
    bars: list[str] = [text(20, 34, "Most Used Languages", size=18, color=THEME["title"], weight=700)]
    bar_x = 20
    bar_y = 48
    bar_w = 280
    cursor = bar_x
    for lang, count in top:
        w = max(2, int(bar_w * count / total))
        color = LANG_COLORS.get(lang, THEME["orange"])
        bars.append(f'<rect x="{cursor}" y="{bar_y}" width="{w}" height="10" rx="5" fill="{color}"/>')
        cursor += w
    for i, (lang, count) in enumerate(top):
        pct = count / total * 100
        color = LANG_COLORS.get(lang, THEME["orange"])
        row_y = y + i * 26
        bars.append(f'<circle cx="{x + 5}" cy="{row_y - 4}" r="5" fill="{color}"/>')
        bars.append(text(x + 18, row_y, f"{lang} {pct:.1f}%", size=13))
    return svg_card(340, 210, "\n  ".join(bars))


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    repos = fetch_all_repos()
    langs = fetch_languages(repos)
    (ASSETS / "stats.svg").write_text(stats_svg(repos, langs), encoding="utf-8")
    (ASSETS / "languages.svg").write_text(languages_svg(langs), encoding="utf-8")
    print(f"Generated cards for {USERNAME}: {len(repos)} repos, {len(langs)} languages")


if __name__ == "__main__":
    main()
