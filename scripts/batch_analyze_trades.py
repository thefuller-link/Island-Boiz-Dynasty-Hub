"""Batch-analyze all trade entries in data/decisions.json and write cache/trade_analysis.json."""

import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone

import yaml

sys.path.insert(0, os.path.dirname(__file__))
from analyze_trade import analyze_trade_assets

REPO_ROOT       = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
DECISIONS_FILE  = os.path.join(REPO_ROOT, "data", "decisions.json")
KTC_CACHE       = os.path.join(REPO_ROOT, "cache", "ktc.json")
SLEEPER_CACHE   = os.path.join(REPO_ROOT, "cache", "sleeper.json")
CONFIG_FILE     = os.path.join(REPO_ROOT, "config.yaml")
OUTPUT_FILE     = os.path.join(REPO_ROOT, "cache", "trade_analysis.json")

DESC_RE = re.compile(
    r"^(?P<owner_a>.+?) sends (?P<assets_a>.+?); (?P<owner_b>.+?) sends (?P<assets_b>.+)$"
)


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _atomic_write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _write_placeholder(note):
    _atomic_write(OUTPUT_FILE, {
        "last_updated": _now_iso(),
        "data_note": note,
        "results": {},
    })
    print(f"cache/trade_analysis.json written (placeholder: {note}).")


def _normalize(name):
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", "", name.lower())).strip()


def _resolve_asset(raw_name, players, picks):
    """Return an asset dict or None. Tries exact name_key, then substring match."""
    key = _normalize(raw_name)

    # exact player match
    for p in players:
        if p.get("name_key") == key:
            return {"type": "player", "name": p["player_name"],
                    "position": p["position"], "value": p["value"]}

    # exact pick match
    for pk in picks:
        if _normalize(pk.get("pick_label", "")) == key:
            return {"type": "pick", "name": pk["pick_label"], "value": pk["value"]}

    # substring player match (any word in key appears in name_key)
    words = key.split()
    best = None
    best_hits = 0
    for p in players:
        pk_key = p.get("name_key", "")
        hits = sum(1 for w in words if w in pk_key)
        if hits > best_hits:
            best_hits = hits
            best = p
    if best and best_hits >= 2:
        return {"type": "player", "name": best["player_name"],
                "position": best["position"], "value": best["value"]}

    # substring pick match
    for pk in picks:
        if key in _normalize(pk.get("pick_label", "")):
            return {"type": "pick", "name": pk["pick_label"], "value": pk["value"]}

    return None


def _parse_description(desc, players, picks):
    """Parse a trade description string into (owner_a, assets_a, owner_b, assets_b, parse_flags)."""
    m = DESC_RE.match(desc.strip())
    if not m:
        return None, [], None, [], [f"Description did not match expected format: {desc!r}"]

    owner_a   = m.group("owner_a").strip()
    owner_b   = m.group("owner_b").strip()
    raw_a     = [n.strip() for n in m.group("assets_a").split(",") if n.strip()]
    raw_b     = [n.strip() for n in m.group("assets_b").split(",") if n.strip()]

    assets_a, assets_b, parse_flags = [], [], []

    for name in raw_a:
        asset = _resolve_asset(name, players, picks)
        if asset:
            assets_a.append(asset)
        else:
            parse_flags.append(f"Unresolved asset (side A): {name!r}")

    for name in raw_b:
        asset = _resolve_asset(name, players, picks)
        if asset:
            assets_b.append(asset)
        else:
            parse_flags.append(f"Unresolved asset (side B): {name!r}")

    return owner_a, assets_a, owner_b, assets_b, parse_flags


def main():
    # Load decisions
    if not os.path.exists(DECISIONS_FILE):
        _write_placeholder("data/decisions.json not found")
        return

    try:
        with open(DECISIONS_FILE, encoding="utf-8") as f:
            decisions = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        _write_placeholder(f"could not parse decisions.json: {e}")
        return

    # Load KTC
    if not os.path.exists(KTC_CACHE):
        _write_placeholder("cache/ktc.json not found -- run sync_ktc.py first")
        return

    try:
        with open(KTC_CACHE, encoding="utf-8") as f:
            ktc = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        _write_placeholder(f"could not parse ktc.json: {e}")
        return

    # Load Sleeper (optional — graceful if missing)
    sleeper = {}
    if os.path.exists(SLEEPER_CACHE):
        try:
            with open(SLEEPER_CACHE, encoding="utf-8") as f:
                sleeper = json.load(f)
        except (json.JSONDecodeError, OSError):
            pass

    # Load team_mode from config (optional)
    team_mode = {}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
            raw_tm = cfg.get("team_mode") or {}
            team_mode = {str(k): str(v) for k, v in raw_tm.items()}
        except Exception:
            pass

    players = ktc.get("players", [])
    picks   = ktc.get("picks", [])

    trade_entries = [e for e in decisions if isinstance(e, dict) and e.get("type") == "trade"]

    results = {}
    for entry in trade_entries:
        entry_id  = entry.get("id", "")
        desc      = entry.get("description", "")
        proposer  = entry.get("proposer", "")

        owner_a, assets_a, owner_b, assets_b, parse_flags = _parse_description(desc, players, picks)

        if owner_a is None or (not assets_a and not assets_b):
            results[entry_id] = {
                "owner_a": None, "owner_b": None,
                "assets_a": [], "assets_b": [],
                "raw_a": None, "raw_b": None,
                "adj_a": None, "adj_b": None,
                "verdict": None, "flags": [],
                "parse_flags": parse_flags,
            }
            continue

        if not assets_a or not assets_b:
            results[entry_id] = {
                "owner_a": owner_a, "owner_b": owner_b,
                "assets_a": assets_a, "assets_b": assets_b,
                "raw_a": None, "raw_b": None,
                "adj_a": None, "adj_b": None,
                "verdict": None, "flags": [],
                "parse_flags": parse_flags,
            }
            continue

        try:
            result = analyze_trade_assets(
                owner_a, assets_a, owner_b, assets_b, ktc, sleeper, team_mode
            )
            result["parse_flags"] = parse_flags
            results[entry_id] = result
        except Exception as e:
            results[entry_id] = {
                "owner_a": owner_a, "owner_b": owner_b,
                "assets_a": assets_a, "assets_b": assets_b,
                "raw_a": None, "raw_b": None,
                "adj_a": None, "adj_b": None,
                "verdict": None, "flags": [],
                "parse_flags": parse_flags + [f"Analysis error: {e}"],
            }

    _atomic_write(OUTPUT_FILE, {
        "last_updated": _now_iso(),
        "data_note": "ok",
        "results": results,
    })
    print(f"cache/trade_analysis.json written ({len(results)} trade(s) analyzed).")


if __name__ == "__main__":
    main()
