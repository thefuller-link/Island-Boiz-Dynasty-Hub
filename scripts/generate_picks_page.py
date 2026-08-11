"""Read cache/picks.json and write site/picks.md."""

import json
import os
import sys

import yaml

CONFIG_FILE = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "config.yaml"))
PICKS_CACHE = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "cache", "picks.json"))
SITE_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "site"))
OUTPUT_FILE = os.path.join(SITE_DIR, "picks.md")

PLACEHOLDER = """\
# Draft Pick Tracker

No pick data available - run `python scripts/sync_picks.py` first.
"""


def _load_config_owners():
    try:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        return cfg.get("owners", [])
    except Exception:
        return []


def _fmt_value(v):
    return str(v) if v is not None else "N/A"


def _flag(pick):
    if pick.get("uncertain"):
        note = pick.get("note") or ""
        return f"[?] {note}".strip() if note else "[?]"
    return ""


def _provenance(pick):
    return pick.get("provenance") or ""


def _pick_label(pick):
    return pick.get("label", f"{pick['year']} Round {pick['round']}")


def _build_our_team_section(picks, our_roster_id, rid_to_name):
    our_name = rid_to_name.get(our_roster_id, f"roster_{our_roster_id}")
    lines = []
    lines.append(f"## Our Team ({our_name})\n")

    our_picks = sorted(
        [p for p in picks if p.get("current_owner") == our_name],
        key=lambda p: (p["year"], p["round"]),
    )

    lines.append("| Pick | Value | Provenance | Flag |")
    lines.append("| --- | --- | --- | --- |")
    if our_picks:
        for p in our_picks:
            lines.append(
                f"| {_pick_label(p)} | {_fmt_value(p.get('value'))} "
                f"| {_provenance(p)} | {_flag(p)} |"
            )
    else:
        lines.append("| No future picks | - | - | - |")
    lines.append("")
    return lines


def _build_full_league_section(picks):
    lines = []
    lines.append("## Full League\n")
    lines.append("| Pick | Owner | Value | Provenance | Flag |")
    lines.append("| --- | --- | --- | --- | --- |")
    sorted_picks = sorted(picks, key=lambda p: (p["year"], p["round"], p["original_owner"]))
    for p in sorted_picks:
        lines.append(
            f"| {_pick_label(p)} | {p.get('current_owner', '')} "
            f"| {_fmt_value(p.get('value'))} "
            f"| {_provenance(p)} | {_flag(p)} |"
        )
    lines.append("")
    return lines


def main():
    os.makedirs(SITE_DIR, exist_ok=True)

    if not os.path.exists(PICKS_CACHE):
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write(PLACEHOLDER)
        print("site/picks.md written (placeholder - cache/picks.json missing).")
        return

    with open(PICKS_CACHE, encoding="utf-8") as f:
        data = json.load(f)

    picks = data.get("picks", [])
    if not picks:
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write(PLACEHOLDER)
        print("site/picks.md written (placeholder - picks array empty).")
        return

    our_roster_id = data.get("our_roster_id")
    last_updated = data.get("last_updated", "")

    # Build roster_id -> display_name from the picks data.
    # We need to identify our team's display_name from our_roster_id.
    # Load config owners to cross-reference via sleeper cache if available.
    sleeper_cache = os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "cache", "sleeper.json")
    )
    rid_to_name = {}
    if os.path.exists(sleeper_cache):
        with open(sleeper_cache, encoding="utf-8") as f:
            sleeper = json.load(f)
        rosters = sleeper.get("rosters", {})
        user_map = sleeper.get("user_map", {})
        for user_id, roster in rosters.items():
            rid = roster.get("roster_id")
            if rid is not None:
                name = user_map.get(user_id, "")
                if name:
                    rid_to_name[rid] = name

    lines = ["# Draft Pick Tracker\n"]

    if our_roster_id and our_roster_id in rid_to_name:
        lines.extend(_build_our_team_section(picks, our_roster_id, rid_to_name))
    else:
        # Fallback: show config owners if we can't resolve our roster
        owners = _load_config_owners()
        lines.append("## Our Team\n")
        lines.append("| Pick | Value | Provenance | Flag |")
        lines.append("| --- | --- | --- | --- |")
        our_picks = sorted(
            [p for p in picks if p.get("current_owner") in owners],
            key=lambda p: (p["year"], p["round"]),
        )
        if our_picks:
            for p in our_picks:
                lines.append(
                    f"| {_pick_label(p)} | {_fmt_value(p.get('value'))} "
                    f"| {_provenance(p)} | {_flag(p)} |"
                )
        else:
            lines.append("| No future picks | - | - | - |")
        lines.append("")

    lines.extend(_build_full_league_section(picks))

    lines.append(f"_Last updated: {last_updated}_")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"site/picks.md written ({len(picks)} picks).")


if __name__ == "__main__":
    main()
