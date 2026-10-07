"""Fetch college player stats from CFBD and write cache/prospects.json."""

import json
import os
import sys
import tempfile
import time
from datetime import datetime, timezone

import requests
import yaml

CFBD_BASE = "https://api.collegefootballdata.com"
REQUEST_READ_TIMEOUT = 120
REQUEST_ATTEMPTS = 3
CONFIG_FILE = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "config.yaml"))
CACHE_FILE = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "cache", "prospects.json"))

# --- Formula constants (dynasty composite score) ---
# score = (yards_per_game_norm * POSITION_WEIGHT) * efficiency_factor * AGE_FACTOR
# efficiency_factor = min(yards_per_opportunity / EFFICIENCY_BASE, EFFICIENCY_CAP)
GAMES_PLAYED_NORM = 12          # Typical FBS regular season game count for normalization
POSITION_WEIGHTS = {            # Dynasty positional scarcity multipliers
    "WR": 1.00,
    "TE": 0.95,
    "RB": 0.80,
    "QB": 0.70,
}
EFFICIENCY_BASE = 10.0          # Yards-per-opportunity divisor; 10 ypOpportunity = excellent
EFFICIENCY_CAP = 1.5            # Cap on efficiency factor to prevent tiny-sample outliers
AGE_FACTOR = 1.0                # Placeholder; future: per-player override via data/prospect_ages.json
SKILL_POSITIONS = set(POSITION_WEIGHTS)

# Minimum yards thresholds to qualify as a primary stat category
PASSING_YDS_MIN = 200           # Below this, player is not classified as QB
RUSHING_YDS_MIN = 150           # Below this, rushing is not the primary category


def _load_season():
    """Return (api_key, season_year)."""
    api_key = os.environ.get("CFBD_API_KEY", "").strip()
    if not api_key:
        print(
            "Error: CFBD_API_KEY environment variable is not set. "
            "Obtain a free key at https://collegefootballdata.com/key and set it as a GitHub Actions secret.",
            file=sys.stderr,
        )
        sys.exit(1)

    season = None
    try:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        season = cfg.get("cfbd_season")
    except Exception:
        pass
    if season is None:
        season = datetime.now().year
    return api_key, int(season)


def _fetch_stats(api_key, year):
    url = f"{CFBD_BASE}/stats/player/season"
    headers = {"Authorization": f"Bearer {api_key}"}
    params = {"year": year, "seasonType": "regular"}
    # The full-season player payload is large and CFBD can be slow, so allow a long read and retry.
    last_exc = None
    for attempt in range(1, REQUEST_ATTEMPTS + 1):
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=(10, REQUEST_READ_TIMEOUT))
            if resp.status_code in (401, 403):
                print(f"Error: CFBD rejected the API key (HTTP {resp.status_code}).", file=sys.stderr)
                sys.exit(1)
            if resp.status_code == 429 or resp.status_code >= 500:
                raise requests.HTTPError(f"HTTP {resp.status_code}")
            resp.raise_for_status()
            return resp.json()
        except (requests.Timeout, requests.ConnectionError, requests.HTTPError) as exc:
            last_exc = exc
            print(f"CFBD attempt {attempt}/{REQUEST_ATTEMPTS} failed: {exc}", file=sys.stderr)
            if attempt < REQUEST_ATTEMPTS:
                time.sleep(5 * attempt)
        except ValueError as exc:
            last_exc = exc
            break
    print(f"Error fetching CFBD stats for year {year}: {last_exc}", file=sys.stderr)
    sys.exit(1)


def _pivot(rows):
    """Group flat stat rows into per-player dicts keyed by (playerId, team)."""
    players = {}
    for row in rows:
        pid = row.get("playerId") or row.get("player_id")
        team = row.get("team", "")
        name = row.get("player", "")
        key = (pid, team)
        if key not in players:
            players[key] = {
                "player": name,
                "team": team,
                "conference": row.get("conference", ""),
                "receivingYards": 0,
                "receivingTD": 0,
                "receivingReceptions": 0,
                "rushingYards": 0,
                "rushingCarries": 0,
                "passingYards": 0,
                "passingCompletions": 0,
                "passingAttempts": 0,
            }
        p = players[key]
        category = (row.get("category") or "").lower()
        stat_type = (row.get("statType") or row.get("stat_type") or "").upper()
        try:
            val = float(row.get("stat", 0) or 0)
        except (TypeError, ValueError):
            val = 0.0

        if category == "receiving":
            if stat_type == "YDS":
                p["receivingYards"] = val
            elif stat_type == "TD":
                p["receivingTD"] = val
            elif stat_type in ("REC", "RECEPTIONS"):
                p["receivingReceptions"] = val
        elif category == "rushing":
            if stat_type == "YDS":
                p["rushingYards"] = val
            elif stat_type in ("CAR", "CARRIES", "ATT"):
                p["rushingCarries"] = val
        elif category == "passing":
            if stat_type == "YDS":
                p["passingYards"] = val
            elif stat_type in ("COMPLETIONS", "COMP"):
                p["passingCompletions"] = val
            elif stat_type == "ATT":
                p["passingAttempts"] = val

    return players


def _infer_position(p):
    """Infer skill position from stat profile; return None if not a tracked position."""
    if p["passingYards"] >= PASSING_YDS_MIN:
        return "QB"
    if p["rushingYards"] >= RUSHING_YDS_MIN and p["rushingYards"] > p["receivingYards"]:
        return "RB"
    if p["receivingYards"] > 0 or p["receivingReceptions"] > 0:
        return "WR"
    return None


def _score(p, position):
    """Return (composite_score, yards_per_game, efficiency_factor)."""
    weight = POSITION_WEIGHTS[position]

    if position == "QB":
        primary_yards = p["passingYards"]
        opportunities = max(p["passingAttempts"], 1)
    elif position == "RB":
        primary_yards = p["rushingYards"] + 0.5 * p["receivingYards"]
        opportunities = max(p["rushingCarries"] + p["receivingReceptions"], 1)
    else:  # WR / TE
        primary_yards = p["receivingYards"]
        opportunities = max(p["receivingReceptions"], 1)

    yards_per_game = primary_yards / GAMES_PLAYED_NORM
    ypo = primary_yards / opportunities
    efficiency_factor = min(ypo / EFFICIENCY_BASE, EFFICIENCY_CAP)

    composite = (yards_per_game * weight) * efficiency_factor * AGE_FACTOR
    return round(composite, 4), round(yards_per_game, 2), round(efficiency_factor, 4)


def main():
    api_key, year = _load_season()

    rows = _fetch_stats(api_key, year)
    if not rows:
        print(
            f"CFBD returned no stats for season {year} (season may not have started yet). "
            "Existing cache/prospects.json left untouched.",
            file=sys.stderr,
        )
        sys.exit(0)

    players = _pivot(rows)

    scored = []
    for (pid, team), p in players.items():
        position = _infer_position(p)
        if position not in SKILL_POSITIONS:
            continue
        composite, ypg, eff = _score(p, position)
        if composite <= 0:
            continue
        scored.append({
            "player": p["player"],
            "team": p["team"],
            "conference": p["conference"],
            "position": position,
            "composite_score": composite,
            "yards_per_game": ypg,
            "efficiency_factor": eff,
            "age_factor": AGE_FACTOR,
            "stat_rank": None,  # assigned below
            "season": year,
        })

    if not scored:
        print(
            f"No scoreable skill-position players found for season {year}. "
            "Existing cache/prospects.json left untouched.",
            file=sys.stderr,
        )
        sys.exit(0)

    scored.sort(key=lambda x: x["composite_score"], reverse=True)
    for i, entry in enumerate(scored, start=1):
        entry["stat_rank"] = i

    payload = {
        "season": year,
        "prospects": scored,
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }

    cache_dir = os.path.dirname(CACHE_FILE)
    os.makedirs(cache_dir, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=cache_dir, suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        os.replace(tmp, CACHE_FILE)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise

    print(
        f"cache/prospects.json written ({len(scored)} skill-position players, "
        f"season={year}, top: {scored[0]['player']} [{scored[0]['position']}] "
        f"score={scored[0]['composite_score']})."
    )


if __name__ == "__main__":
    main()
