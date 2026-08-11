"""Derive draft pick ownership and write cache/picks.json."""

import json
import os
import sys
import tempfile
from datetime import datetime, timezone

import requests
import yaml

SLEEPER_BASE = "https://api.sleeper.app/v1"
CONFIG_FILE = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "config.yaml"))
SLEEPER_CACHE = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "cache", "sleeper.json"))
KTC_CACHE = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "cache", "ktc.json"))
PICKS_CACHE = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "cache", "picks.json"))
OVERRIDES_FILE = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "data", "pick_overrides.json"))

ROUND_ORDINAL = {1: "1st", 2: "2nd", 3: "3rd", 4: "4th"}


def _load_config():
    with open(CONFIG_FILE, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    league_id = cfg.get("league_id")
    if not league_id:
        print("Error: league_id not found in config.yaml.", file=sys.stderr)
        sys.exit(1)
    return str(league_id), cfg.get("owners", [])


def _verify_caches():
    missing = []
    if not os.path.exists(SLEEPER_CACHE):
        missing.append(("cache/sleeper.json", "sync_sleeper.py"))
    if not os.path.exists(KTC_CACHE):
        missing.append(("cache/ktc.json", "sync_ktc.py"))
    if missing:
        for fname, script in missing:
            print(f"Error: {fname} not found - run python scripts/{script} first.", file=sys.stderr)
        sys.exit(1)


def _build_roster_index(sleeper):
    """roster_id (int) -> display_name."""
    rosters = sleeper.get("rosters", {})
    user_map = sleeper.get("user_map", {})
    index = {}
    for user_id, roster in rosters.items():
        rid = roster.get("roster_id")
        if rid is None:
            continue
        name = user_map.get(user_id, "")
        if name:
            index[rid] = name
    return index


def _find_our_roster_id(sleeper, owners):
    """Find the roster_id shared by our co-owner group (match any config owner name)."""
    user_map = sleeper.get("user_map", {})
    rosters = sleeper.get("rosters", {})
    owners_set = set(owners)
    our_user_ids = {uid for uid, name in user_map.items() if name in owners_set}
    if not our_user_ids:
        return None
    for user_id, roster in rosters.items():
        if user_id in our_user_ids:
            return roster.get("roster_id")
        co_owners = roster.get("co_owners") or []
        if any(uid in our_user_ids for uid in co_owners):
            return roster.get("roster_id")
    return None


def _get_base_year(sleeper):
    nfl_state = sleeper.get("nfl_state") or {}
    season_str = nfl_state.get("season")
    if season_str:
        try:
            return int(season_str)
        except ValueError:
            pass
    return datetime.now().year


def _ktc_value(year, round_num, ktc_by_label):
    ordinal = ROUND_ORDINAL.get(round_num, f"{round_num}th")
    for tier, source in [
        ("Mid", "ktc_mid_default"),
        ("Early", "ktc_early_default"),
        ("Late", "ktc_late_default"),
    ]:
        label = f"{year} {tier} {ordinal}"
        if label in ktc_by_label:
            return ktc_by_label[label], label, source
    return None, None, "unmatched"


def main():
    league_id, owners = _load_config()
    _verify_caches()

    with open(SLEEPER_CACHE, encoding="utf-8") as f:
        sleeper = json.load(f)
    with open(KTC_CACHE, encoding="utf-8") as f:
        ktc = json.load(f)

    rid_to_name = _build_roster_index(sleeper)
    our_roster_id = _find_our_roster_id(sleeper, owners)
    ktc_by_label = {p["pick_label"]: p["value"] for p in ktc.get("picks", [])}

    base_year = _get_base_year(sleeper)
    years = [str(base_year + i) for i in range(3)]

    # Default ledger: every team owns all its own picks.
    # Key: (year_str, round_int, original_roster_id_int)
    ledger = {}
    for rid, name in rid_to_name.items():
        for year in years:
            for rnd in range(1, 4):
                value, ktc_label, value_source = _ktc_value(year, rnd, ktc_by_label)
                ledger[(year, rnd, rid)] = {
                    "year": year,
                    "round": rnd,
                    "label": f"{year} Round {rnd}",
                    "ktc_label": ktc_label,
                    "original_owner": name,
                    "current_owner": name,
                    "provenance": None,
                    "value": value,
                    "value_source": value_source,
                    "uncertain": False,
                    "note": None,
                    "source": "sleeper_default",
                }

    # Live fetch: traded picks are the authoritative source — no stale fallback.
    url = f"{SLEEPER_BASE}/league/{league_id}/traded_picks"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        traded = resp.json()
    except Exception as exc:
        print(f"Error fetching traded picks from Sleeper API: {exc}", file=sys.stderr)
        sys.exit(1)

    # Apply trades to ledger.
    # Sleeper traded_picks uses roster IDs for owner_id (original) and roster_id (current).
    for entry in traded:
        year = str(entry.get("season", ""))
        rnd = entry.get("round")
        orig_rid = entry.get("owner_id")
        curr_rid = entry.get("roster_id")

        if not year or rnd is None or orig_rid is None or curr_rid is None:
            continue

        key = (year, rnd, orig_rid)
        if key not in ledger:
            continue  # Pick outside our year window or unknown team

        curr_name = rid_to_name.get(curr_rid)
        orig_name = rid_to_name.get(orig_rid)
        uncertain = curr_name is None or orig_name is None

        pick = ledger[key]
        pick["current_owner"] = curr_name if curr_name else f"roster_{curr_rid}"
        if pick["current_owner"] != pick["original_owner"]:
            pick["provenance"] = f"via {pick['original_owner']}"
        else:
            pick["provenance"] = None
        pick["uncertain"] = uncertain
        pick["source"] = "sleeper_traded"

    # Apply manual overrides.
    if os.path.exists(OVERRIDES_FILE):
        with open(OVERRIDES_FILE, encoding="utf-8") as f:
            try:
                overrides = json.load(f)
            except json.JSONDecodeError:
                overrides = []
        for ov in overrides:
            year = str(ov.get("year", ""))
            rnd = ov.get("round")
            orig_name = ov.get("original_owner", "")
            matched_key = None
            for (ky, kr, krid), pick in ledger.items():
                if ky == year and kr == rnd and pick["original_owner"] == orig_name:
                    matched_key = (ky, kr, krid)
                    break
            if matched_key:
                pick = ledger[matched_key]
                if ov.get("current_owner"):
                    pick["current_owner"] = ov["current_owner"]
                    if pick["current_owner"] != pick["original_owner"]:
                        pick["provenance"] = f"via {pick['original_owner']}"
                    else:
                        pick["provenance"] = None
                if ov.get("note"):
                    pick["note"] = ov["note"]
                if "uncertain" in ov:
                    pick["uncertain"] = ov["uncertain"]
                pick["source"] = "manual"
            else:
                # Override references a pick not in the ledger — add it.
                value, ktc_label, value_source = _ktc_value(year, rnd or 0, ktc_by_label)
                curr_name = ov.get("current_owner", orig_name)
                new_pick = {
                    "year": year,
                    "round": rnd,
                    "label": f"{year} Round {rnd}",
                    "ktc_label": ktc_label,
                    "original_owner": orig_name,
                    "current_owner": curr_name,
                    "provenance": f"via {orig_name}" if curr_name != orig_name else None,
                    "value": value,
                    "value_source": value_source,
                    "uncertain": ov.get("uncertain", False),
                    "note": ov.get("note"),
                    "source": "manual",
                }
                ledger[(year, rnd or 0, -len(ledger))] = new_pick

    picks = sorted(
        ledger.values(),
        key=lambda p: (p["year"], p["round"], p["original_owner"]),
    )

    payload = {
        "our_roster_id": our_roster_id,
        "picks": picks,
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }

    cache_dir = os.path.dirname(PICKS_CACHE)
    os.makedirs(cache_dir, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=cache_dir, suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        os.replace(tmp_path, PICKS_CACHE)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

    unmatched = sum(1 for p in picks if p["value_source"] == "unmatched")
    uncertain_count = sum(1 for p in picks if p["uncertain"])
    print(
        f"cache/picks.json written ({len(picks)} picks, "
        f"our_roster_id={our_roster_id}, "
        f"{unmatched} unmatched KTC values, {uncertain_count} uncertain)."
    )


if __name__ == "__main__":
    main()
