"""Interactive CLI for evaluating dynasty trade proposals."""

import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone

import yaml

REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
CONFIG_FILE = os.path.join(REPO_ROOT, "config.yaml")
KTC_CACHE = os.path.join(REPO_ROOT, "cache", "ktc.json")
SLEEPER_CACHE = os.path.join(REPO_ROOT, "cache", "sleeper.json")
DECISIONS_FILE = os.path.join(REPO_ROOT, "data", "decisions.json")

REBUILD_WEIGHT = 1.20
RETOOL_WEIGHT = 1.05
CONTEND_WEIGHT = 0.85
MODE_WEIGHTS = {"rebuilding": REBUILD_WEIGHT, "retooling": RETOOL_WEIGHT, "contending": CONTEND_WEIGHT}
STALENESS_HOURS = 48
REDUNDANCY_THRESHOLD = 2
SUGGESTION_COUNT = 5


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize_name(name):
    name = name.lower()
    name = re.sub(r"[^\w\s]", "", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def load_config():
    if not os.path.exists(CONFIG_FILE):
        print(f"Error: config.yaml not found.", file=sys.stderr)
        sys.exit(1)
    with open(CONFIG_FILE, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    owners = cfg.get("owners")
    if not owners:
        print("Error: 'owners' key missing from config.yaml.", file=sys.stderr)
        sys.exit(1)
    team_mode = cfg.get("team_mode") or {}
    return [str(o) for o in owners], {str(k): str(v) for k, v in team_mode.items()}


def load_caches():
    """Load KTC and Sleeper JSON caches. Exit if missing."""
    missing = []
    if not os.path.exists(KTC_CACHE):
        missing.append(("cache/ktc.json", "python scripts/sync_ktc.py"))
    if not os.path.exists(SLEEPER_CACHE):
        missing.append(("cache/sleeper.json", "python scripts/sync_sleeper.py"))
    if missing:
        for fname, cmd in missing:
            print(f"Error: {fname} not found -run `{cmd}` first.", file=sys.stderr)
        sys.exit(1)

    with open(KTC_CACHE, encoding="utf-8") as f:
        ktc = json.load(f)
    with open(SLEEPER_CACHE, encoding="utf-8") as f:
        sleeper = json.load(f)
    return ktc, sleeper


def check_staleness(ktc):
    """Warn if KTC cache is older than STALENESS_HOURS."""
    ts = ktc.get("last_updated", "")
    if not ts:
        return
    try:
        # Handle both 'Z' suffix and offset-aware formats
        ts_clean = ts.replace("Z", "+00:00")
        from datetime import datetime, timezone
        updated = datetime.fromisoformat(ts_clean)
        age_hours = (datetime.now(timezone.utc) - updated).total_seconds() / 3600
        if age_hours > STALENESS_HOURS:
            print(f"Warning: KTC values last updated {ts} ({age_hours:.0f}h ago) -may not reflect current market.")
    except Exception:
        pass


def _find_player(name_key, players):
    """Return exact match player entry or None."""
    for p in players:
        if p["name_key"] == name_key:
            return p
    return None


def _suggest_players(name_key, players):
    """Return up to SUGGESTION_COUNT players whose name_key contains any input word."""
    words = name_key.split()
    scored = []
    for p in players:
        pk = p["name_key"]
        hits = sum(1 for w in words if w in pk)
        if hits:
            scored.append((hits, p))
    scored.sort(key=lambda x: -x[0])
    return [p for _, p in scored[:SUGGESTION_COUNT]]


def _find_pick(label_key, picks):
    """Return exact-normalized pick match or None."""
    for pk in picks:
        if _normalize_name(pk["pick_label"]) == label_key:
            return pk
    return None


def prompt_owner(owners, label="Who are you?", exclude=None):
    available = [o for o in owners if o != exclude]
    print(f"\n{label}")
    for i, name in enumerate(available, 1):
        print(f"  {i}. {name}")
    lower_names = [o.lower() for o in available]
    while True:
        raw = input("Enter number or name: ").strip()
        try:
            idx = int(raw) - 1
            if 0 <= idx < len(available):
                return available[idx]
        except ValueError:
            pass
        if raw.lower() in lower_names:
            return available[lower_names.index(raw.lower())]
        print(f"  Invalid. Enter a number 1-{len(available)} or an exact name.")


def prompt_assets(side_label, players, picks):
    """Prompt user to enter players/picks for one side. Returns list of asset dicts."""
    assets = []
    print(f"\n{side_label} assets -enter player names or pick labels (e.g. '2026 Mid 1st').")
    print("  Press Enter on a blank line when done.")
    while True:
        raw = input("  Asset: ").strip()
        if not raw:
            if not assets:
                print("  At least one asset is required.")
                continue
            break

        key = _normalize_name(raw)

        # Try player match first
        player = _find_player(key, players)
        if player:
            assets.append({"type": "player", "name": player["player_name"],
                           "position": player["position"], "value": player["value"]})
            print(f"    Added: {player['player_name']} ({player['position']}) -value {player['value']}")
            continue

        # Try pick match
        pick = _find_pick(key, picks)
        if pick:
            assets.append({"type": "pick", "name": pick["pick_label"], "value": pick["value"]})
            print(f"    Added: {pick['pick_label']} -value {pick['value']}")
            continue

        # No match -show suggestions
        suggestions = _suggest_players(key, players)
        print(f"    No match for '{raw}'.")
        if suggestions:
            print("    Closest player matches:")
            for i, s in enumerate(suggestions, 1):
                print(f"      {i}. {s['player_name']} ({s['position']}, {s['team']}) -{s['value']}")
        print("    Pick options (enter number to select, or type pick label):")
        for i, pk in enumerate(picks, 1):
            print(f"      {i}. {pk['pick_label']} -{pk['value']}")
        sel = input("    Select number, re-type name, or press Enter to skip: ").strip()
        if not sel:
            continue
        try:
            idx = int(sel) - 1
            if 0 <= idx < len(suggestions):
                p = suggestions[idx]
                assets.append({"type": "player", "name": p["player_name"],
                               "position": p["position"], "value": p["value"]})
                print(f"    Added: {p['player_name']}")
                continue
            pick_idx = idx - len(suggestions)
            if 0 <= pick_idx < len(picks):
                pk = picks[pick_idx]
                assets.append({"type": "pick", "name": pk["pick_label"], "value": pk["value"]})
                print(f"    Added: {pk['pick_label']}")
                continue
        except ValueError:
            pass
        # Try again with the typed re-entry
        key2 = _normalize_name(sel)
        player2 = _find_player(key2, players)
        if player2:
            assets.append({"type": "player", "name": player2["player_name"],
                           "position": player2["position"], "value": player2["value"]})
            print(f"    Added: {player2['player_name']}")
            continue
        pick2 = _find_pick(key2, picks)
        if pick2:
            assets.append({"type": "pick", "name": pick2["pick_label"], "value": pick2["value"]})
            print(f"    Added: {pick2['pick_label']}")
            continue
        print(f"    Could not match '{sel}' -skipped.")

    return assets


# ---------------------------------------------------------------------------
# Value calculations
# ---------------------------------------------------------------------------

def _pick_weight(owner, team_mode):
    mode = team_mode.get(owner, "").lower()
    weight = MODE_WEIGHTS.get(mode)
    if weight is None:
        return 1.0, True  # missing mode
    return weight, False


def compute_totals(assets_a, assets_b, owner_a, owner_b, team_mode):
    """
    Returns (raw_a, raw_b, adj_a, adj_b, flags).
    adj_* apply pick-weight multiplier based on the RECEIVING owner's team_mode.
    """
    raw_a = sum(a["value"] for a in assets_a)
    raw_b = sum(a["value"] for a in assets_b)

    flags = []
    adj_a = 0
    adj_b = 0

    # Side A sends → Side B receives
    weight_b, missing_b = _pick_weight(owner_b, team_mode)
    for a in assets_a:
        if a["type"] == "pick":
            adj_b += a["value"] * weight_b
        else:
            adj_b += a["value"]
    if missing_b:
        flags.append(f"team_mode not set for {owner_b} -picks weighted at 1.0x")

    # Side B sends → Side A receives
    weight_a, missing_a = _pick_weight(owner_a, team_mode)
    for a in assets_b:
        if a["type"] == "pick":
            adj_a += a["value"] * weight_a
        else:
            adj_a += a["value"]
    if missing_a and not missing_b:
        flags.append(f"team_mode not set for {owner_a} -picks weighted at 1.0x")

    return raw_a, raw_b, adj_a, adj_b, flags


def redundancy_flags(acquiring_owner, new_assets, sleeper, user_map):
    """Return flags for positional redundancy on the receiving team."""
    flags = []

    # Find the owner's user_id via user_map (display_name → user_id is reversed)
    owner_user_id = None
    for uid, display in (user_map or {}).items():
        if display.lower() == acquiring_owner.lower():
            owner_user_id = uid
            break

    if not owner_user_id:
        return flags  # Can't determine roster without mapping

    roster = sleeper.get("rosters", {}).get(owner_user_id, {})
    rostered_ids = roster.get("players") or []
    player_meta = sleeper.get("player_metadata", {})

    for asset in new_assets:
        if asset["type"] != "player":
            continue
        acquired_pos = asset.get("position", "")
        if not acquired_pos:
            continue
        count = sum(
            1 for pid in rostered_ids
            if player_meta.get(pid, {}).get("position", "") == acquired_pos
        )
        if count >= REDUNDANCY_THRESHOLD:
            flags.append(
                f"{acquiring_owner} already has {count} rostered {acquired_pos}"
            )

    return flags


def analyze_trade_assets(owner_a, assets_a, owner_b, assets_b, ktc, sleeper, team_mode):
    """Compute trade analysis without any I/O. Returns a result dict."""
    user_map = sleeper.get("user_map", {}) if sleeper else {}

    raw_a, raw_b, adj_a, adj_b, calc_flags = compute_totals(
        assets_a, assets_b, owner_a, owner_b, team_mode
    )
    red_flags_a = redundancy_flags(owner_a, assets_b, sleeper, user_map)
    red_flags_b = redundancy_flags(owner_b, assets_a, sleeper, user_map)
    all_flags = calc_flags + red_flags_a + red_flags_b

    diff = abs(adj_a - adj_b)
    higher = adj_a if adj_a >= adj_b else adj_b
    pct = (diff / higher * 100) if higher else 0
    if pct <= 1.0:
        verdict = "approximately even"
    elif adj_a > adj_b:
        verdict = f"favors {owner_a} by {diff:.0f} ({pct:.1f}%)"
    else:
        verdict = f"favors {owner_b} by {diff:.0f} ({pct:.1f}%)"

    return {
        "owner_a": owner_a,
        "owner_b": owner_b,
        "assets_a": assets_a,
        "assets_b": assets_b,
        "raw_a": raw_a,
        "raw_b": raw_b,
        "adj_a": round(adj_a, 1),
        "adj_b": round(adj_b, 1),
        "verdict": verdict,
        "flags": all_flags,
    }


# ---------------------------------------------------------------------------
# Output + decision-log write
# ---------------------------------------------------------------------------

def print_verdict(owner_a, owner_b, assets_a, assets_b, raw_a, raw_b, adj_a, adj_b, flags):
    print("\n" + "=" * 50)
    print("TRADE ANALYSIS")
    print("=" * 50)

    a_names = ", ".join(a["name"] for a in assets_a)
    b_names = ", ".join(a["name"] for a in assets_b)
    print(f"\n{owner_a} sends: {a_names}")
    print(f"{owner_b} sends: {b_names}")

    print(f"\nRaw values:  {owner_a} gives {raw_a}  |  {owner_b} gives {raw_b}")
    print(f"Adj values:  {owner_a} gets  {adj_a:.0f}  |  {owner_b} gets  {adj_b:.0f}")

    diff = abs(adj_a - adj_b)
    higher = adj_a if adj_a >= adj_b else adj_b
    pct = (diff / higher * 100) if higher else 0

    if pct <= 1.0:
        verdict = "approximately even"
    elif adj_a > adj_b:
        verdict = f"favors {owner_a} by {diff:.0f} ({pct:.1f}%)"
    else:
        verdict = f"favors {owner_b} by {diff:.0f} ({pct:.1f}%)"

    print(f"\nVerdict: {verdict}")

    if flags:
        print("\nConsiderations:")
        for f in flags[:2]:
            print(f"  - {f}")

    print("=" * 50)
    return verdict, flags


def write_decision_log(owner_a, assets_a, owner_b, assets_b, verdict, flags, owners):
    """Append a trade entry to data/decisions.json."""
    a_names = ", ".join(a["name"] for a in assets_a)
    b_names = ", ".join(a["name"] for a in assets_b)
    description = f"{owner_a} sends {a_names}; {owner_b} sends {b_names}"
    rationale = f"KTC analysis: {verdict}."
    if flags:
        rationale += " Notes: " + "; ".join(flags[:2])

    responses = {o: "pending" for o in owners}
    responses[owner_a] = "approve"

    now = datetime.now(timezone.utc)
    entry_id = now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"
    entry = {
        "id": entry_id,
        "date": now.strftime("%Y-%m-%d"),
        "type": "trade",
        "proposer": owner_a,
        "description": description,
        "responses": responses,
        "rationale": rationale,
    }

    entries = []
    if os.path.exists(DECISIONS_FILE):
        with open(DECISIONS_FILE, encoding="utf-8") as f:
            try:
                entries = json.load(f)
            except json.JSONDecodeError:
                entries = []

    entries.append(entry)
    os.makedirs(os.path.dirname(DECISIONS_FILE), exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(DECISIONS_FILE), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(entries, fh, indent=2)
            fh.write("\n")
        os.replace(tmp_path, DECISIONS_FILE)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise

    print(f"\nOK: Decision logged. ID: {entry_id}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    owners, team_mode = load_config()
    ktc, sleeper = load_caches()
    check_staleness(ktc)

    players = ktc.get("players", [])
    picks = ktc.get("picks", [])
    user_map = sleeper.get("user_map", {})

    print("\nIslandBoiiiiiz Trade Analyzer")
    print("  KTC values loaded:", len(players), "players,", len(picks), "picks")

    owner_a = prompt_owner(owners, "Side A -which owner is proposing the trade?")
    owner_b = prompt_owner(owners, "Side B -which owner is on the other side?", exclude=owner_a)

    assets_a = prompt_assets(f"Side A ({owner_a}) sends", players, picks)
    assets_b = prompt_assets(f"Side B ({owner_b}) sends", players, picks)

    result = analyze_trade_assets(owner_a, assets_a, owner_b, assets_b, ktc, sleeper, team_mode)

    verdict, flags = print_verdict(
        owner_a, owner_b, assets_a, assets_b,
        result["raw_a"], result["raw_b"], result["adj_a"], result["adj_b"], result["flags"]
    )

    print("\nLog this trade to the decision log? (y/N): ", end="")
    ans = input().strip().lower()
    if ans == "y":
        write_decision_log(owner_a, assets_a, owner_b, assets_b, verdict, flags, owners)
    else:
        print("Not logged.")


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\nCancelled.")
        sys.exit(0)
