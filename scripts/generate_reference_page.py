"""Render league settings + group agreements sections (embedded at the bottom of the Today page)."""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from html_utils import stale_banner
from html import escape

REPO_ROOT      = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
SETTINGS_CACHE = os.path.join(REPO_ROOT, "cache", "league_settings.json")
EXTRA_FILE     = os.path.join(REPO_ROOT, "data", "league_rules_extra.json")

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

WAIVER_TYPE_LABEL = {0: "Free agent (immediate)", 1: "Standard (waiver priority)", 2: "FAAB (blind bid)"}
LEAGUE_TYPE_LABEL = {0: "Redraft", 1: "Keeper", 2: "Dynasty"}


def _scoring_type_label(scoring_settings):
    rec = scoring_settings.get("rec", 0) or 0
    bonus_te = scoring_settings.get("bonus_rec_te", 0) or 0
    if rec == 0:
        return "Standard (no PPR)"
    base = "Half-PPR" if rec == 0.5 else ("Full PPR" if rec == 1.0 else f"Custom PPR ({rec} pts/rec)")
    if bonus_te and bonus_te > 0:
        return f"{base} + TE premium (+{bonus_te})"
    return base


def _roster_summary(positions):
    starters = [p for p in positions if p not in ("BN", "IR")]
    bench = positions.count("BN")
    counts = {}
    for p in starters:
        counts[p] = counts.get(p, 0) + 1
    return starters, counts, bench


def _li(label, value):
    return f'<li><span class="k">{escape(label)}</span> {escape(str(value))}</li>'


def _render_settings_section(data):
    settings = data.get("settings", {})
    scoring  = data.get("scoring_settings", {})
    positions = data.get("roster_positions", [])
    last_updated = data.get("last_updated", "")

    league_type = LEAGUE_TYPE_LABEL.get(settings.get("type", 0), f"type {settings.get('type')}")
    scoring_type = _scoring_type_label(scoring)
    starters, counts, bench = _roster_summary(positions)
    waiver_type = WAIVER_TYPE_LABEL.get(settings.get("waiver_type", 0), str(settings.get("waiver_type")))
    waiver_budget = settings.get("waiver_budget")
    trade_deadline = settings.get("trade_deadline", 0)
    td_label = f"End of Week {trade_deadline}" if trade_deadline else "None"
    num_teams = settings.get("num_teams", "?")
    reserve_slots = settings.get("reserve_slots", 0)
    taxi_slots = settings.get("taxi_slots", 0)
    taxi_years = settings.get("taxi_years", 0)
    draft_rounds = settings.get("draft_rounds", "?")
    pick_trading = settings.get("pick_trading", 0)
    max_keepers = settings.get("max_keepers", 0) or 0

    ts_str = last_updated[:19].replace("T", " ") + " UTC" if last_updated else "unknown"

    # Format subsection
    format_items = [
        _li("League type:", league_type),
        _li("Teams:", num_teams),
        _li("Scoring:", scoring_type),
        _li("Rookie draft rounds:", draft_rounds),
        _li("Pick trading:", "Enabled" if pick_trading else "Disabled"),
        _li("Trade deadline:", td_label),
        _li("Trade review period:", f"{settings.get('trade_review_days', 0)} day(s)"),
    ]
    format_html = f'<h3>Format</h3><ul class="rule-list">{"".join(format_items)}</ul>'

    # Roster subsection
    roster_items = [_li(f"Total starters:", len(starters))]
    for pos, cnt in counts.items():
        roster_items.append(f'<li class="sub"><span class="k">&nbsp;&nbsp;{escape(pos)}:</span> {cnt}</li>')
    roster_items.append(_li("Bench slots:", bench))
    if reserve_slots:
        roster_items.append(_li("IR slots:", reserve_slots))
    if taxi_slots:
        roster_items.append(_li("Taxi squad:", f"{taxi_slots} slots, {taxi_years} year(s) eligibility"))
    roster_html = f'<h3>Roster</h3><ul class="rule-list">{"".join(roster_items)}</ul>'

    # Waivers
    waiver_items = [_li("Waiver type:", waiver_type)]
    if waiver_budget:
        waiver_items.append(_li("FAAB budget:", f"${waiver_budget}"))
    waiver_html = f'<h3>Waivers</h3><ul class="rule-list">{"".join(waiver_items)}</ul>'

    # Keeper
    keeper_html = ""
    if max_keepers > 0:
        k_items = [_li("Max keepers per team:", max_keepers)]
        keeper_deadline = settings.get("keeper_deadline")
        if keeper_deadline:
            k_items.append(_li("Keeper deadline:", f"Week {keeper_deadline}"))
        keeper_cost = settings.get("keeper_cost")
        if keeper_cost is not None:
            k_items.append(_li("Keeper cost:", keeper_cost))
        keeper_html = f'<h3>Keeper Rules (Sleeper-configured)</h3><ul class="rule-list">{"".join(k_items)}</ul>'

    # Scoring settings
    non_zero = {k: v for k, v in scoring.items() if v and v != 0}
    score_items = []
    for key, val in sorted(non_zero.items(), key=lambda x: SCORING_LABEL.get(x[0], x[0])):
        label = SCORING_LABEL.get(key, key)
        score_items.append(f'<li><span class="k">{escape(label)}:</span> {val:g}</li>')
    scoring_html = f'<h3>Scoring Settings</h3><ul class="scoring-list">{"".join(score_items)}</ul>'

    footer = f'<div class="section-meta">Auto-synced from Sleeper &middot; Last synced: {escape(ts_str)}</div>'

    return "\n".join([format_html, roster_html, waiver_html, keeper_html, scoring_html, footer])


def _render_manual_section(data):
    if data is None:
        return '<p class="banner-missing">No group agreements on file.</p>'
    rules = data.get("rules", [])
    if not rules:
        return '<p class="banner-missing">No group agreements on file.</p>'

    categories = {}
    for entry in rules:
        cat = entry.get("category", "General")
        categories.setdefault(cat, []).append(entry.get("rule", ""))

    parts = []
    for cat, cat_rules in categories.items():
        items = "".join(f'<li>{escape(r)}</li>' for r in cat_rules)
        parts.append(f'<h3>{escape(cat)}</h3><ul class="rule-list">{items}</ul>')

    author = escape(data.get("last_updated_by", "unknown"))
    date   = escape(data.get("last_updated", "unknown"))
    footer = f'<div class="section-meta">Manually maintained -- edit data/league_rules_extra.json to update &middot; Last updated by: {author} on {date}</div>'
    return "\n".join(parts) + "\n" + footer


def _load_json(path):
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def render_reference_sections():
    """Return the League Settings and Group Agreements section cards as HTML."""
    settings_data = _load_json(SETTINGS_CACHE)
    extra_data    = _load_json(EXTRA_FILE)

    # League settings section
    if settings_data is None:
        settings_html = (
            '<p class="banner-missing">League settings not yet synced -- '
            'run python scripts/sync_league_settings.py</p>'
        )
        settings_banner = ""
    else:
        settings_banner = stale_banner("League settings", settings_data.get("last_updated"))
        settings_html = _render_settings_section(settings_data)

    # Manual rules section
    extra_banner = ""
    if extra_data:
        extra_banner = stale_banner("Group agreements", extra_data.get("last_updated"))
    manual_html = _render_manual_section(extra_data)

    return f"""<div class="section-card">
  <h2>League Settings</h2>
  {settings_banner}{settings_html}
</div>

<div class="section-card">
  <h2>Group Agreements</h2>
  {extra_banner}{manual_html}
</div>"""
