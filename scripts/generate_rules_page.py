"""Read cache/league_settings.json + data/league_rules_extra.json and write site/rules.md."""

import json
import os
import sys
import tempfile
from datetime import datetime, timezone

REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
SETTINGS_CACHE = os.path.join(REPO_ROOT, "cache", "league_settings.json")
EXTRA_FILE = os.path.join(REPO_ROOT, "data", "league_rules_extra.json")
OUTPUT_FILE = os.path.join(REPO_ROOT, "site", "rules.md")

# Human-readable labels for Sleeper scoring keys
SCORING_LABEL = {
    "rec": "Reception",
    "rec_yd": "Receiving yard",
    "rec_td": "Receiving TD",
    "rec_2pt": "Receiving 2-pt conversion",
    "rush_yd": "Rushing yard",
    "rush_td": "Rushing TD",
    "rush_2pt": "Rushing 2-pt conversion",
    "pass_yd": "Passing yard",
    "pass_td": "Passing TD",
    "pass_int": "Interception thrown",
    "pass_2pt": "Passing 2-pt conversion",
    "fum_lost": "Fumble lost",
    "fum_rec_td": "Fumble recovery TD",
    "sack": "Sack (defense)",
    "ff": "Forced fumble (defense)",
    "xpm": "Extra point made",
    "xpmiss": "Extra point missed",
    "fgm_0_19": "FG made 0-19 yards",
    "fgm_20_29": "FG made 20-29 yards",
    "fgm_30_39": "FG made 30-39 yards",
    "fgm_40_49": "FG made 40-49 yards",
    "fgm_50_59": "FG made 50-59 yards",
    "fgmiss": "FG missed",
    "st_td": "Special teams TD",
    "st_fum_rec": "Special teams fumble recovery",
    "pts_allow_0": "Pts allowed: 0 (defense)",
    "pts_allow_1_6": "Pts allowed: 1-6 (defense)",
    "pts_allow_7_13": "Pts allowed: 7-13 (defense)",
    "pts_allow_14_20": "Pts allowed: 14-20 (defense)",
    "pts_allow_21_27": "Pts allowed: 21-27 (defense)",
    "pts_allow_28_34": "Pts allowed: 28-34 (defense)",
    "pts_allow_35p": "Pts allowed: 35+ (defense)",
    "bonus_rec_te": "TE premium bonus",
    "bonus_rec_wr": "WR reception bonus",
    "bonus_rec_rb": "RB reception bonus",
}

WAIVER_TYPE_LABEL = {
    0: "Free agent (immediate)",
    1: "Standard (waiver priority)",
    2: "FAAB (blind bid)",
}

LEAGUE_TYPE_LABEL = {
    0: "Redraft",
    1: "Keeper",
    2: "Dynasty",
}


def _roster_summary(positions):
    """Summarize roster_positions into starter breakdown and bench count."""
    starters = [p for p in positions if p != "BN" and p != "IR"]
    bench = positions.count("BN")
    ir = positions.count("IR")
    counts = {}
    for p in starters:
        counts[p] = counts.get(p, 0) + 1
    return starters, counts, bench, ir


def _trade_deadline_label(week_num):
    if not week_num or week_num == 0:
        return "None"
    return f"End of Week {week_num}"


def _scoring_type_label(scoring_settings):
    rec = scoring_settings.get("rec", 0) or 0
    bonus_te = scoring_settings.get("bonus_rec_te", 0) or 0
    if rec == 0:
        return "Standard (no PPR)"
    if rec == 0.5:
        base = "Half-PPR"
    elif rec == 1.0:
        base = "Full PPR"
    else:
        base = f"Custom PPR ({rec} pts/rec)"
    if bonus_te and bonus_te > 0:
        return f"{base} + TE premium (+{bonus_te})"
    return base


def _render_auto_section(data):
    lines = []
    settings = data.get("settings", {})
    scoring = data.get("scoring_settings", {})
    positions = data.get("roster_positions", [])
    last_updated = data.get("last_updated", "unknown")

    league_type = LEAGUE_TYPE_LABEL.get(settings.get("type", 0), f"type {settings.get('type')}")
    scoring_type = _scoring_type_label(scoring)
    starters, counts, bench, ir_slots = _roster_summary(positions)
    waiver_type = WAIVER_TYPE_LABEL.get(settings.get("waiver_type", 0), str(settings.get("waiver_type")))
    waiver_budget = settings.get("waiver_budget")
    trade_deadline = _trade_deadline_label(settings.get("trade_deadline"))
    num_teams = settings.get("num_teams", "?")
    reserve_slots = settings.get("reserve_slots", 0)
    taxi_slots = settings.get("taxi_slots", 0)
    taxi_years = settings.get("taxi_years", 0)
    draft_rounds = settings.get("draft_rounds", "?")
    pick_trading = settings.get("pick_trading", 0)

    lines.append("## League Settings")
    lines.append("")
    lines.append("_Auto-synced from Sleeper_")
    lines.append("")

    lines.append("### Format")
    lines.append("")
    lines.append(f"- **League type:** {league_type}")
    lines.append(f"- **Teams:** {num_teams}")
    lines.append(f"- **Scoring:** {scoring_type}")
    lines.append(f"- **Rookie draft rounds:** {draft_rounds}")
    lines.append(f"- **Pick trading:** {'Enabled' if pick_trading else 'Disabled'}")
    lines.append(f"- **Trade deadline:** {trade_deadline}")
    lines.append(f"- **Trade review period:** {settings.get('trade_review_days', 0)} day(s)")
    lines.append("")

    lines.append("### Roster")
    lines.append("")
    lines.append(f"- **Total starters:** {len(starters)}")
    for pos, cnt in counts.items():
        lines.append(f"  - {pos}: {cnt}")
    lines.append(f"- **Bench slots:** {bench}")
    if reserve_slots:
        lines.append(f"- **IR slots:** {reserve_slots}")
    if taxi_slots:
        lines.append(f"- **Taxi squad:** {taxi_slots} slots, {taxi_years} year(s) eligibility")
    lines.append("")

    lines.append("### Waivers")
    lines.append("")
    lines.append(f"- **Waiver type:** {waiver_type}")
    if waiver_budget:
        lines.append(f"- **FAAB budget:** ${waiver_budget}")
    lines.append("")

    # Keeper section only if max_keepers > 0
    max_keepers = settings.get("max_keepers", 0) or 0
    if max_keepers > 0:
        lines.append("### Keeper Rules (Sleeper-configured)")
        lines.append("")
        lines.append(f"- **Max keepers per team:** {max_keepers}")
        keeper_deadline = settings.get("keeper_deadline")
        if keeper_deadline:
            lines.append(f"- **Keeper deadline:** Week {keeper_deadline}")
        keeper_cost = settings.get("keeper_cost")
        if keeper_cost is not None:
            lines.append(f"- **Keeper cost:** {keeper_cost}")
        lines.append("")

    lines.append("### Scoring Settings")
    lines.append("")
    non_zero = {k: v for k, v in scoring.items() if v and v != 0}
    for key, val in sorted(non_zero.items(), key=lambda x: SCORING_LABEL.get(x[0], x[0])):
        label = SCORING_LABEL.get(key, key)
        lines.append(f"- **{label}:** {val:g}")
    lines.append("")

    ts = last_updated[:19].replace("T", " ") if last_updated != "unknown" else "unknown"
    lines.append(f"_Last synced: {ts} UTC_")
    return lines


def _render_manual_section(data):
    lines = []
    lines.append("## Group Agreements")
    lines.append("")
    lines.append("_Manually maintained -- edit `data/league_rules_extra.json` to update_")
    lines.append("")

    if data is None:
        lines.append("_No group agreements on file._")
        lines.append("")
        return lines

    rules = data.get("rules", [])
    if not rules:
        lines.append("_No group agreements on file._")
        lines.append("")
        return lines

    # Group by category
    categories = {}
    for entry in rules:
        cat = entry.get("category", "General")
        categories.setdefault(cat, []).append(entry.get("rule", ""))

    for cat, cat_rules in categories.items():
        lines.append(f"### {cat}")
        lines.append("")
        for rule in cat_rules:
            lines.append(f"- {rule}")
        lines.append("")

    author = data.get("last_updated_by", "unknown")
    date = data.get("last_updated", "unknown")
    lines.append(f"_Last updated by: {author} on {date}_")
    return lines


def _atomic_write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def main():
    # Load league settings cache
    settings_data = None
    if os.path.exists(SETTINGS_CACHE):
        try:
            with open(SETTINGS_CACHE, encoding="utf-8") as f:
                settings_data = json.load(f)
        except json.JSONDecodeError as exc:
            print(f"Warning: could not parse {SETTINGS_CACHE}: {exc}", file=sys.stderr)

    # Load manual extra rules
    extra_data = None
    if os.path.exists(EXTRA_FILE):
        try:
            with open(EXTRA_FILE, encoding="utf-8") as f:
                extra_data = json.load(f)
        except json.JSONDecodeError as exc:
            print(f"Warning: could not parse {EXTRA_FILE}: {exc}", file=sys.stderr)

    lines = ["# League Rules", ""]

    if settings_data is None:
        lines.append("## League Settings")
        lines.append("")
        lines.append("_League settings not yet synced -- run `python scripts/sync_league_settings.py`_")
        lines.append("")
    else:
        lines.extend(_render_auto_section(settings_data))

    lines.append("")
    lines.append("---")
    lines.append("")
    lines.extend(_render_manual_section(extra_data))

    _atomic_write(OUTPUT_FILE, "\n".join(lines) + "\n")
    print("site/rules.md written.")


if __name__ == "__main__":
    main()
