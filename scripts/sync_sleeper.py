"""Fetch league data from the Sleeper API and write cache/sleeper.json."""

import json
import os
import sys
from datetime import datetime, timezone

import requests
import yaml

SLEEPER_BASE = "https://api.sleeper.app/v1"
CACHE_FILE = os.path.join(os.path.dirname(__file__), "..", "cache", "sleeper.json")
CONFIG_FILE = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "config.yaml")
)


def _get(url, timeout=10):
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def _load_league_id():
    # Env var overrides config.yaml (useful for one-off testing).
    if league_id := os.environ.get("SLEEPER_LEAGUE_ID"):
        return league_id
    try:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
        league_id = config.get("league_id")
        if league_id:
            return str(league_id)
    except Exception:
        pass
    print(
        "Error: league_id not found in config.yaml and SLEEPER_LEAGUE_ID env var is not set.",
        file=sys.stderr,
    )
    sys.exit(1)


def main():
    league_id = _load_league_id()

    # Stale fallback: all network calls happen before any write.
    # If any call fails, the existing cache is left untouched.
    try:
        nfl_state = _get(f"{SLEEPER_BASE}/state/nfl")
        week = nfl_state.get("week", 1)

        rosters_raw = _get(f"{SLEEPER_BASE}/league/{league_id}/rosters")
        rosters = {
            r["owner_id"]: r
            for r in rosters_raw
            if r.get("owner_id")
        }

        users_raw = _get(f"{SLEEPER_BASE}/league/{league_id}/users")
        user_map = {
            u["user_id"]: u.get("display_name") or u.get("username", "")
            for u in users_raw
            if u.get("user_id")
        }

        matchups = _get(f"{SLEEPER_BASE}/league/{league_id}/matchups/{week}")

        transactions = _get(
            f"{SLEEPER_BASE}/league/{league_id}/transactions/{week}"
        )

        trending_raw = _get(
            f"{SLEEPER_BASE}/players/nfl/trending/add?lookback_hours=24&limit=200"
        )
        trending_adds = [item["player_id"] for item in trending_raw]

        all_players = _get(f"{SLEEPER_BASE}/players/nfl", timeout=30)
        player_metadata = {
            pid: {
                "player_id": pid,
                "full_name": data.get("full_name", ""),
                "position": data.get("position", ""),
                "years_exp": data.get("years_exp"),
            }
            for pid, data in all_players.items()
            if data.get("full_name")
        }

    except Exception as exc:
        print(f"Error fetching from Sleeper API: {exc}", file=sys.stderr)
        sys.exit(1)

    payload = {
        "nfl_state": nfl_state,
        "rosters": rosters,
        "user_map": user_map,
        "matchups": matchups,
        "transactions": transactions,
        "trending_adds": trending_adds,
        "player_metadata": player_metadata,
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }

    cache_path = os.path.normpath(CACHE_FILE)
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    print(
        f"cache/sleeper.json updated — "
        f"{len(rosters)} rosters, {len(user_map)} users, "
        f"{len(trending_adds)} trending, {len(player_metadata)} players, week {week}."
    )


if __name__ == "__main__":
    main()
