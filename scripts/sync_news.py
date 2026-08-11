"""Fetch RotoWire NFL RSS and filter to roster-relevant players; write cache/news.json."""

import json
import os
import sys
from datetime import datetime, timezone

import feedparser
import requests
import yaml

ROTOWIRE_RSS = "https://www.rotowire.com/rss/news.php?sport=NFL"
SLEEPER_CACHE = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "cache", "sleeper.json")
)
NEWS_CACHE = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "cache", "news.json")
)
CONFIG_FILE = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "config.yaml")
)

# Category order determines output ordering when multiple tiers match.
TIER_ORDER = ["rostered", "trending", "rookie", "watchlist"]


def load_sleeper_cache():
    if not os.path.exists(SLEEPER_CACHE):
        print(
            f"Error: {SLEEPER_CACHE} not found. Run sync_sleeper.py first.",
            file=sys.stderr,
        )
        sys.exit(1)

    with open(SLEEPER_CACHE, encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as exc:
            print(f"Error: {SLEEPER_CACHE} is not valid JSON: {exc}", file=sys.stderr)
            sys.exit(1)

    for key in ("rosters", "trending_adds", "player_metadata"):
        if key not in data:
            print(
                f"Error: {SLEEPER_CACHE} is missing required key '{key}'. "
                "Re-run sync_sleeper.py.",
                file=sys.stderr,
            )
            sys.exit(1)

    return data


def build_tiers(sleeper_data):
    player_metadata = sleeper_data["player_metadata"]
    rosters = sleeper_data["rosters"]
    trending_adds = sleeper_data["trending_adds"]

    def name_of(pid):
        return player_metadata.get(str(pid), {}).get("full_name", "").strip().lower()

    rostered_names = set()
    for roster in rosters.values():
        for pid in roster.get("players") or []:
            n = name_of(pid)
            if n:
                rostered_names.add(n)

    trending_names = set()
    for pid in trending_adds:
        n = name_of(pid)
        if n:
            trending_names.add(n)

    rookie_names = set()
    for meta in player_metadata.values():
        if meta.get("years_exp") == 0:
            n = meta.get("full_name", "").strip().lower()
            if n:
                rookie_names.add(n)

    watchlist_names = set()
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
            for entry in config.get("watchlist") or []:
                watchlist_names.add(str(entry).strip().lower())
        except Exception:
            pass  # unreadable config → empty watchlist

    return {
        "rostered": rostered_names,
        "trending": trending_names,
        "rookie": rookie_names,
        "watchlist": watchlist_names,
    }


def match_categories(title, description, tiers):
    text = f"{title} {description}".lower()
    matched = []
    for category in TIER_ORDER:
        for name in tiers[category]:
            if name and name in text:
                matched.append(category)
                break
    return matched


def main():
    # Validate sleeper cache before any network call (stale fallback path first).
    sleeper_data = load_sleeper_cache()
    tiers = build_tiers(sleeper_data)

    try:
        response = requests.get(ROTOWIRE_RSS, timeout=10)
        response.raise_for_status()
        feed = feedparser.parse(response.content)
    except Exception as exc:
        print(f"Error fetching RotoWire RSS: {exc}", file=sys.stderr)
        sys.exit(1)

    items = []
    for entry in feed.entries:
        title = entry.get("title", "")
        description = entry.get("summary", entry.get("description", ""))
        categories = match_categories(title, description, tiers)
        if not categories:
            continue
        items.append({
            "title": title,
            "description": description,
            "published": entry.get("published", ""),
            "link": entry.get("link", ""),
            "categories": categories,
        })

    payload = {
        "items": items,
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }

    with open(NEWS_CACHE, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    print(
        f"cache/news.json updated — "
        f"{len(items)} items kept from {len(feed.entries)} RSS entries."
    )


if __name__ == "__main__":
    main()
