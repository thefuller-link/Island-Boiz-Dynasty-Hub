"""Suggest league-wide dynasty trades from Sleeper rosters, KTC values and pick ownership.

Examples:
  python scripts/suggest_trades.py                      # our team, auto-detected deficiencies
  python scripts/suggest_trades.py --need WR,TE         # explicit positional need
  python scripts/suggest_trades.py --partner BigFcknDaddy --partner yungtt --random 0
  python scripts/suggest_trades.py --give "2027 Mid 1st" --write
"""

import argparse
import itertools
import json
import os
import random
import re
import sys
import tempfile
from datetime import datetime, timezone

import yaml

sys.path.insert(0, os.path.dirname(__file__))
from analyze_trade import analyze_trade_assets

REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
CONFIG_FILE = os.path.join(REPO_ROOT, "config.yaml")
KTC_CACHE = os.path.join(REPO_ROOT, "cache", "ktc.json")
SLEEPER_CACHE = os.path.join(REPO_ROOT, "cache", "sleeper.json")
PICKS_CACHE = os.path.join(REPO_ROOT, "cache", "picks.json")
OUTPUT_FILE = os.path.join(REPO_ROOT, "cache", "trade_suggestions.json")

POSITIONS = ("QB", "RB", "WR", "TE")
# Starter-quality depth per position (1QB/2RB/2WR/1TE + 2 FLEX + 1 SUPERFLEX).
STARTERS = {"QB": 2, "RB": 3, "WR": 4, "TE": 2}
NEED_RATIO = 0.90      # position strength below this share of league mean = deficiency
SURPLUS_RATIO = 1.10
MIN_TARGET_VALUE = 1500
MAX_OFFER_PIECES = 3
PIECE_WEIGHTS = (1.0, 0.8, 0.65)   # consolidation: the 2nd/3rd piece is worth less to the receiver
FAIR_LOW, FAIR_HIGH = 0.97, 1.20   # offered (perceived) value vs target value
CANDIDATE_POOL = 18
MAX_PARTNERS = 2


def _normalize(name):
    name = re.sub(r"\s+", " ", re.sub(r"[^\w\s]", "", name.lower())).strip()
    return re.sub(r" (jr|sr|ii|iii|iv|v)$", "", name)  # Sleeper and KTC disagree on suffixes


def _load_json(path, label, script):
    if not os.path.exists(path):
        print(f"Error: {label} not found - run python scripts/{script} first.", file=sys.stderr)
        sys.exit(1)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_teams(sleeper, ktc, picks_cache):
    """Return {roster_id: team dict} with KTC-valued players and owned picks."""
    user_map = sleeper.get("user_map", {})
    meta = sleeper.get("player_metadata", {})
    by_key = {_normalize(p["player_name"]): p for p in ktc.get("players", [])}

    teams = {}
    for owner_id, roster in sleeper.get("rosters", {}).items():
        rid = roster.get("roster_id")
        name = user_map.get(owner_id)
        if rid is None or not name:
            continue
        pids = set(roster.get("players") or []) | set(roster.get("reserve") or []) | set(roster.get("taxi") or [])
        players = []
        for pid in pids:
            m = meta.get(pid) or {}
            k = by_key.get(_normalize(m.get("full_name", "")))
            if k and k["position"] in POSITIONS and k["value"] > 0:
                players.append({"type": "player", "name": k["player_name"],
                                "position": k["position"], "value": k["value"]})
        teams[rid] = {"roster_id": rid, "name": name,
                      "co_owner_ids": set([owner_id] + list(roster.get("co_owners") or [])),
                      "players": sorted(players, key=lambda p: -p["value"]), "picks": []}

    name_to_rid = {t["name"]: rid for rid, t in teams.items()}
    for pk in picks_cache.get("picks", []):
        rid = name_to_rid.get(pk.get("current_owner"))
        if rid is not None and pk.get("value"):
            label = pk.get("ktc_label") or pk["label"]
            teams[rid]["picks"].append({"type": "pick", "name": f"{label} (orig. {pk['original_owner']})"
                                        if pk["original_owner"] != pk["current_owner"] else label,
                                        "value": pk["value"]})
    for t in teams.values():
        t["picks"].sort(key=lambda p: -p["value"])
    return teams


def position_profile(team):
    """Starter-value per position and the ranked players at each position."""
    by_pos = {pos: [p for p in team["players"] if p["position"] == pos] for pos in POSITIONS}
    strength = {pos: sum(p["value"] for p in by_pos[pos][:STARTERS[pos]]) for pos in POSITIONS}
    return by_pos, strength


def classify_needs(teams):
    """Return {rid: {"strength", "needs", "surplus", "by_pos"}} relative to league mean."""
    profiles = {rid: position_profile(t) for rid, t in teams.items()}
    n = len(profiles) or 1
    mean = {pos: sum(s[pos] for _, s in profiles.values()) / n or 1 for pos in POSITIONS}
    out = {}
    for rid, (by_pos, strength) in profiles.items():
        ratio = {pos: strength[pos] / mean[pos] for pos in POSITIONS}
        out[rid] = {
            "by_pos": by_pos,
            "ratio": ratio,
            "needs": [p for p in sorted(POSITIONS, key=lambda x: ratio[x]) if ratio[p] < NEED_RATIO],
            "surplus": [p for p in sorted(POSITIONS, key=lambda x: -ratio[x]) if ratio[p] > SURPLUS_RATIO],
        }
    return out


def tradable_pool(team, prof):
    """Depth players, players at surplus positions beyond the core, and all picks."""
    pool = list(team["picks"])
    for pos in POSITIONS:
        core = STARTERS[pos] - (1 if pos in prof["surplus"] else 0)
        pool.extend(prof["by_pos"][pos][core:])
    return pool


def perceived_value(assets):
    vals = sorted((a["value"] for a in assets), reverse=True)
    return sum(v * PIECE_WEIGHTS[i] for i, v in enumerate(vals))


def build_offers(target_value, pool):
    """Combos of up to MAX_OFFER_PIECES pool assets that fairly match target_value."""
    cands = sorted(pool, key=lambda a: abs(a["value"] - target_value))[:CANDIDATE_POOL]
    for size in range(1, MAX_OFFER_PIECES + 1):
        for combo in itertools.combinations(cands, size):
            pv = perceived_value(combo)
            if target_value * FAIR_LOW <= pv <= target_value * FAIR_HIGH:
                yield list(combo), pv


def find_team(teams, ident, cfg_owners, user_map):
    ident = (ident or "").lower()
    for t in teams.values():
        if t["name"].lower() == ident:
            return t
    if ident:
        return None
    ours = {o.lower() for o in cfg_owners}
    our_ids = {uid for uid, n in user_map.items() if n.lower() in ours}
    for t in teams.values():
        if t["co_owner_ids"] & our_ids:
            return t
    return None


def suggest(teams, profiles, me, needs, give, partner, team_mode, sleeper, ktc, top):
    results = []
    me_prof = profiles[me["roster_id"]]
    pool = tradable_pool(me, me_prof)
    if give:
        keys = [_normalize(g) for g in give]
        pool = [a for a in me["players"] + me["picks"] if any(k in _normalize(a["name"]) for k in keys)]
        if not pool:
            print("Error: none of the --give assets are on this roster.", file=sys.stderr)
            sys.exit(1)
    pool_names = {a["name"] for a in pool}

    for rid, other in teams.items():
        if rid == me["roster_id"] or (partner and other["name"].lower() not in partner):
            continue
        o_prof = profiles[rid]
        o_pool = {a["name"] for a in tradable_pool(other, o_prof)}
        targets = [p for p in other["players"]
                   if p["position"] in needs and p["value"] >= MIN_TARGET_VALUE]
        for target in targets:
            offer_pool = [a for a in pool if a["name"] != target["name"]]
            for offer, pv in build_offers(target["value"], offer_pool):
                if any(a["type"] == "player" and a["position"] == target["position"] for a in offer):
                    continue  # sending the position we are trying to fill
                res = analyze_trade_assets(me["name"], offer, other["name"], [target],
                                           ktc, sleeper, team_mode)
                fit = sum(1 for a in offer if a["type"] == "player" and a["position"] in o_prof["needs"])
                if any(a["type"] == "pick" for a in offer):
                    fit += 0.5
                balance = 1 - abs(pv - target["value"]) / target["value"]
                score = balance + 0.25 * fit + (0.3 if target["name"] in o_pool else 0) \
                    - 0.05 * (len(offer) - 1)
                res_flags = [f for f in res["flags"] if "team_mode not set" not in f]
                results.append({
                    "partner": other["name"], "give": offer, "get": [target],
                    "offered_perceived_value": round(pv), "target_value": target["value"],
                    "partner_needs": o_prof["needs"], "verdict": res["verdict"],
                    "flags": res_flags, "score": round(score, 3),
                })
    results.sort(key=lambda r: -r["score"])
    seen, out = set(), []
    for r in results:
        key = (r["partner"], tuple(sorted(a["name"] for a in r["give"])), r["get"][0]["name"])
        per_partner = sum(1 for o in out if o["partner"] == r["partner"])
        if key in seen or per_partner >= 3:
            continue
        seen.add(key)
        out.append(r)
        if len(out) >= top:
            break
    return out


def _atomic_write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--team", help="Sleeper display name to build trades for (default: our team)")
    ap.add_argument("--need", help="Comma-separated positions to target, e.g. WR,TE (default: detected deficiencies)")
    ap.add_argument("--give", action="append", help="Only offer assets matching this name (repeatable)")
    ap.add_argument("--partner", action="append", help="Trade partner display name (repeatable, max 2 incl. --random)")
    ap.add_argument("--random", type=int, default=0, metavar="N",
                    help="Add N randomly chosen partners (combined with --partner, max 2 total)")
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--write", action="store_true", help="Write results to cache/trade_suggestions.json")
    args = ap.parse_args()

    with open(CONFIG_FILE, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    cfg_owners = [str(o) for o in cfg.get("owners") or []]
    cfg_mode = {str(k): str(v) for k, v in (cfg.get("team_mode") or {}).items()}

    sleeper = _load_json(SLEEPER_CACHE, "cache/sleeper.json", "sync_sleeper.py")
    ktc = _load_json(KTC_CACHE, "cache/ktc.json", "sync_ktc.py")
    picks_cache = _load_json(PICKS_CACHE, "cache/picks.json", "sync_picks.py")

    teams = build_teams(sleeper, ktc, picks_cache)
    me = find_team(teams, args.team, cfg_owners, sleeper.get("user_map", {}))
    if not me:
        print(f"Error: team {args.team!r} not found. Teams: " + ", ".join(sorted(t["name"] for t in teams.values())),
              file=sys.stderr)
        sys.exit(1)

    by_name = {t["name"].lower(): t for t in teams.values() if t is not me}
    partners = [p.lower() for p in args.partner or []]
    unknown = [p for p in partners if p not in by_name]
    if unknown:
        print(f"Error: unknown partner(s) {unknown}. Teams: " + ", ".join(sorted(t["name"] for t in by_name.values())),
              file=sys.stderr)
        sys.exit(1)
    if len(set(partners)) + max(args.random, 0) > MAX_PARTNERS:
        print(f"Error: at most {MAX_PARTNERS} partners (--partner + --random).", file=sys.stderr)
        sys.exit(1)
    partners = list(dict.fromkeys(partners))
    partners += random.sample([n for n in by_name if n not in partners], max(args.random, 0))
    if partners:
        print("Partners: " + ", ".join(by_name[p]["name"] for p in partners))

    profiles = classify_needs(teams)
    prof = profiles[me["roster_id"]]

    if args.need:
        needs = [p.strip().upper() for p in args.need.split(",") if p.strip()]
        bad = [p for p in needs if p not in POSITIONS]
        if bad:
            print(f"Error: unknown position(s) {bad}; use {', '.join(POSITIONS)}.", file=sys.stderr)
            sys.exit(1)
    else:
        needs = prof["needs"]

    # Our co-owned roster shares one team_mode; apply the first configured owner's setting.
    team_mode = {}
    if not args.team:
        team_mode[me["name"]] = next((cfg_mode[o] for o in cfg_owners if o in cfg_mode), "")

    print(f"\nTeam: {me['name']}")
    print("Position strength vs league mean: " + ", ".join(f"{p} {prof['ratio'][p]:.2f}" for p in POSITIONS))
    print(f"Deficiencies: {', '.join(prof['needs']) or 'none'} | Surplus: {', '.join(prof['surplus']) or 'none'}")
    print(f"Targeting: {', '.join(needs) or 'none'}")
    if not needs:
        print("No needs detected; pass --need to force a target position.")
        return

    out = suggest(teams, profiles, me, needs, args.give, set(partners), team_mode, sleeper, ktc, args.top)
    if not out:
        print("\nNo balanced trades found. Try a wider --need, other --give assets, or no --partner.")
    for i, r in enumerate(out, 1):
        give = ", ".join(f"{a['name']} ({a['value']})" for a in r["give"])
        get = ", ".join(f"{a['name']} ({a['position']}, {a['value']})" for a in r["get"])
        print(f"\n{i}. {r['partner']}  [partner needs: {', '.join(r['partner_needs']) or 'none'}]")
        print(f"   You send:    {give}")
        print(f"   You receive: {get}")
        print(f"   Verdict: {r['verdict']}")
        for flag in r["flags"][:2]:
            print(f"   - {flag}")

    if args.write:
        _atomic_write(OUTPUT_FILE, {
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "team": me["name"], "needs": needs, "suggestions": out,
        })
        print("\ncache/trade_suggestions.json written.")


if __name__ == "__main__":
    main()
