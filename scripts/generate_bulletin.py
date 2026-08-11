"""Merge prospect stats + consensus ranks and write site/bulletin.md."""

import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta

PROSPECTS_CACHE = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "cache", "prospects.json"))
CONSENSUS_CACHE = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "cache", "consensus.json"))
SITE_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "site"))
OUTPUT_FILE = os.path.join(SITE_DIR, "bulletin.md")

DIVERGENCE_THRESHOLD = 5    # Minimum rank gap to flag in the bulletin
BULLETIN_TARGET = 15        # Default number of entries
BULLETIN_MAX = 20           # Maximum entries (ties at position 15 may push past target)
STALE_DAYS = 8              # Days after which a cache is considered stale

PLACEHOLDER = """\
# Prospect Bulletin

Prospect data unavailable -- run `python scripts/sync_prospects.py` first.
"""


def _normalize(name):
    name = name.lower()
    name = re.sub(r"[^a-z0-9 ]", "", name)
    return re.sub(r"\s+", " ", name).strip()


def _parse_ts(ts_str):
    if not ts_str:
        return None
    try:
        return datetime.fromisoformat(ts_str)
    except ValueError:
        return None


def _stale_warning(label, ts_str):
    ts = _parse_ts(ts_str)
    if ts is None:
        return None
    now = datetime.now(timezone.utc)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    if (now - ts) > timedelta(days=STALE_DAYS):
        days_ago = (now - ts).days
        return f"> **Warning:** {label} data is {days_ago} days old -- run the sync script to refresh."
    return None


def _divergence_note(stat_rank, consensus_rank):
    diff = consensus_rank - stat_rank
    if abs(diff) <= DIVERGENCE_THRESHOLD:
        return ""
    if diff > 0:
        # stat rank is better (lower number) than consensus
        return (
            f"stat rank #{stat_rank}, consensus #{consensus_rank} -- "
            "efficiency spiking, market hasn't caught up"
        )
    else:
        return (
            f"stat rank #{stat_rank}, consensus #{consensus_rank} -- "
            "market leader, stats haven't backed it up"
        )


def _sort_key(entry):
    sr = entry.get("stat_rank")
    cr = entry.get("consensus_rank")
    if sr is not None and cr is not None:
        return min(sr, cr)
    return sr if sr is not None else (cr if cr is not None else 9999)


def main():
    os.makedirs(SITE_DIR, exist_ok=True)

    if not os.path.exists(PROSPECTS_CACHE):
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write(PLACEHOLDER)
        print("site/bulletin.md written (placeholder - cache/prospects.json missing).")
        return

    with open(PROSPECTS_CACHE, encoding="utf-8") as f:
        prospects_data = json.load(f)

    prospects = prospects_data.get("prospects", [])
    prospects_ts = prospects_data.get("last_updated", "")

    consensus_board = []
    consensus_ts = ""
    consensus_missing = False
    if os.path.exists(CONSENSUS_CACHE):
        with open(CONSENSUS_CACHE, encoding="utf-8") as f:
            consensus_data = json.load(f)
        consensus_board = consensus_data.get("board", [])
        consensus_ts = consensus_data.get("last_updated", "")
    else:
        consensus_missing = True

    # Build name-keyed lookups
    stat_by_name = {_normalize(p["player"]): p for p in prospects}
    consensus_by_name = {_normalize(e["name"]): e for e in consensus_board}

    all_names = set(stat_by_name) | set(consensus_by_name)
    merged = []
    for name_key in all_names:
        sp = stat_by_name.get(name_key)
        cp = consensus_by_name.get(name_key)
        entry = {
            "player": (sp or cp).get("player") or (sp or cp).get("name"),
            "position": (sp or {}).get("position") or (cp or {}).get("position", ""),
            "school": (sp or {}).get("team") or (cp or {}).get("school", ""),
            "stat_rank": sp.get("stat_rank") if sp else None,
            "consensus_rank": cp.get("consensus_rank") if cp else None,
        }
        merged.append(entry)

    # Sort and select top entries
    merged.sort(key=_sort_key)

    selected = []
    for entry in merged:
        if len(selected) < BULLETIN_TARGET:
            selected.append(entry)
        elif len(selected) < BULLETIN_MAX:
            # Include ties at the cut-off rank
            last_key = _sort_key(selected[-1])
            if _sort_key(entry) == last_key:
                selected.append(entry)
            else:
                break
        else:
            break

    # Build page
    now_ts = datetime.now(timezone.utc).isoformat()
    lines = ["# Prospect Bulletin\n"]

    warnings = []
    w = _stale_warning("Prospect stats", prospects_ts)
    if w:
        warnings.append(w)
    if not consensus_missing:
        w = _stale_warning("Consensus board", consensus_ts)
        if w:
            warnings.append(w)

    if consensus_missing:
        lines.append("> **Note:** Consensus data not available -- run `python scripts/sync_consensus.py` after updating `data/consensus_board.json`.\n")
    for w in warnings:
        lines.append(w + "\n")

    if selected:
        lines.append("| # | Player | Pos | School | Stat Rank | Consensus Rank | Notes |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- |")
        for i, entry in enumerate(selected, start=1):
            sr = entry["stat_rank"]
            cr = entry["consensus_rank"]
            sr_str = f"#{sr}" if sr is not None else "N/A"
            cr_str = f"#{cr}" if cr is not None else "N/A"
            note = _divergence_note(sr, cr) if (sr is not None and cr is not None) else ""
            lines.append(
                f"| {i} | {entry['player']} | {entry['position']} | {entry['school']} "
                f"| {sr_str} | {cr_str} | {note} |"
            )
    else:
        lines.append("_No prospect data to display._\n")

    lines.append("")
    lines.append(f"_Last updated: {now_ts}_")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"site/bulletin.md written ({len(selected)} entries).")


if __name__ == "__main__":
    main()
