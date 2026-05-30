#!/usr/bin/env python3
"""Generate README.md from GitHub starred repositories grouped by month."""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


GITHUB_API = "https://api.github.com/user/starred"
ACCEPT_HEADER = "application/vnd.github.v3.star+json"
PER_PAGE = 100


def fetch_starred(token: str) -> list[dict]:
    stars: list[dict] = []
    page = 1

    while True:
        url = f"{GITHUB_API}?per_page={PER_PAGE}&page={page}"
        request = urllib.request.Request(
            url,
            headers={
                "Accept": ACCEPT_HEADER,
                "Authorization": f"Bearer {token}",
                "User-Agent": "erbanku-stars-generator",
            },
        )

        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                payload = json.load(response)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"GitHub API error {exc.code}: {body}") from exc

        if not payload:
            break

        for item in payload:
            repo = item.get("repo") or {}
            starred_at = item.get("starred_at")
            if not starred_at:
                continue

            stars.append(
                {
                    "starred_at": starred_at,
                    "full_name": repo.get("full_name", ""),
                    "html_url": repo.get("html_url", ""),
                    "description": repo.get("description") or "",
                }
            )

        if len(payload) < PER_PAGE:
            break
        page += 1

    return stars


def month_key(starred_at: str) -> str:
    dt = datetime.fromisoformat(starred_at.replace("Z", "+00:00"))
    return dt.astimezone(timezone.utc).strftime("%Y-%m")


def escape_description(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def build_readme(stars: list[dict]) -> str:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for star in stars:
        grouped[month_key(star["starred_at"])].append(star)

    months = sorted(grouped.keys(), reverse=True)

    lines = [
        "# GitHub Stars",
        "",
        "## Contents",
        "",
    ]

    for month in months:
        lines.append(f"- [{month}](#{month}) ({len(grouped[month])})")

    lines.append("")

    for month in months:
        lines.extend([f"## {month}", ""])
        month_stars = sorted(
            grouped[month],
            key=lambda item: item["starred_at"],
            reverse=True,
        )
        for star in month_stars:
            name = star["full_name"]
            url = star["html_url"] or f"https://github.com/{name}"
            description = escape_description(star["description"])
            if description:
                lines.append(f"- [{name}]({url}) - {description}")
            else:
                lines.append(f"- [{name}]({url})")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("GITHUB_TOKEN is required", file=sys.stderr)
        return 1

    output = Path(os.environ.get("OUTPUT_PATH", "README.md"))

    stars = fetch_starred(token)
    readme = build_readme(stars)
    output.write_text(readme, encoding="utf-8")
    print(f"Wrote {len(stars)} stars across {len(set(month_key(s['starred_at']) for s in stars))} months to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
