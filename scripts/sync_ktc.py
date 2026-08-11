"""Fetch KeepTradeCut dynasty trade values and write to cache/ktc.json."""

import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone

import requests
import yaml

REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
CACHE_FILE = os.path.join(REPO_ROOT, "cache", "ktc.json")
CONFIG_FILE = os.path.join(REPO_ROOT, "config.yaml")

# Undocumented public endpoint used by the dynasty community.
# Returns an HTML page with a `playersArray` JS variable containing
# both players (various positions) and draft picks (position = "RDP").
KTC_URL = "https://keeptradecut.com/dynasty-rankings?format=2"
REQUEST_TIMEOUT = 30

# Which KTC value type to use: "superflex" or "oneqb"
# Superflex is the more common dynasty format.
KTC_VALUE_TYPE = "superflex"


def _normalize_name(name):
    """Lowercase, strip punctuation, collapse whitespace."""
    name = name.lower()
    name = re.sub(r"[^\w\s]", "", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def _load_value_type():
    """Read ktc_value_type from config.yaml; default to superflex."""
    try:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        return cfg.get("ktc_value_type", KTC_VALUE_TYPE)
    except Exception:
        return KTC_VALUE_TYPE


def _stale_last_updated():
    """Return last_updated from existing cache file, or None if unavailable."""
    if not os.path.exists(CACHE_FILE):
        return None
    try:
        with open(CACHE_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("last_updated")
    except Exception:
        return None


def _fetch_html():
    """Fetch the KTC rankings page. Returns response text or raises."""
    resp = requests.get(KTC_URL, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp.text


def _extract_players_array(html):
    """Extract the `playersArray` JSON from KTC's HTML page."""
    m = re.search(r"var\s+playersArray\s*=\s*(\[.*?\]);\s*var\s+", html, re.DOTALL)
    if not m:
        raise ValueError("Could not find `playersArray` in KTC page — site structure may have changed.")
    return json.loads(m.group(1))


def _parse_ktc_data(raw_data, value_type):
    """Split raw KTC list into (players, picks) using the chosen value type."""
    if not isinstance(raw_data, list):
        raise ValueError(f"Expected JSON array, got {type(raw_data).__name__}")

    value_key = "superflexValues" if value_type == "superflex" else "oneQBValues"

    players = []
    picks = []

    for entry in raw_data:
        name = entry.get("playerName", "")
        position = entry.get("position", "")
        values_obj = entry.get(value_key) or {}
        value = int(values_obj.get("value") or 0)
        team = entry.get("team") or ""

        if position == "RDP":
            if name:
                picks.append({"pick_label": name, "value": value})
        else:
            if name:
                players.append({
                    "player_name": name,
                    "name_key": _normalize_name(name),
                    "position": position.upper() if position else "",
                    "team": team,
                    "value": value,
                })

    return players, picks


def main():
    value_type = _load_value_type()
    stale_ts = _stale_last_updated()

    try:
        html = _fetch_html()
    except requests.RequestException as exc:
        msg = f"Error fetching KTC page: {exc}"
        if stale_ts:
            msg += f"  (stale cache from {stale_ts} preserved)"
        print(msg, file=sys.stderr)
        sys.exit(1)

    try:
        raw_data = _extract_players_array(html)
    except (ValueError, json.JSONDecodeError) as exc:
        print(f"Error extracting KTC data: {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        players, picks = _parse_ktc_data(raw_data, value_type)
    except ValueError as exc:
        print(f"Error parsing KTC data structure: {exc}", file=sys.stderr)
        sys.exit(1)

    if not players and not picks:
        print("Error: KTC response parsed to empty — unexpected format.", file=sys.stderr)
        sys.exit(1)

    now = datetime.now(timezone.utc)
    payload = {
        "players": players,
        "picks": picks,
        "value_type": value_type,
        "last_updated": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(CACHE_FILE), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
            f.write("\n")
        os.replace(tmp_path, CACHE_FILE)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise

    print(
        f"cache/ktc.json written ({len(players)} players, {len(picks)} picks, "
        f"value_type={value_type})."
    )


if __name__ == "__main__":
    main()
