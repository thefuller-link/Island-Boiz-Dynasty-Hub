"""Read pick/prospect/usage caches and write site/rookies.html."""

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from html_utils import page_shell, stale_banner, missing_section, _atomic_write
from html import escape

REPO_ROOT     = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
USAGE_CACHE   = os.path.join(REPO_ROOT, "cache", "usage.json")
PICKS_CACHE   = os.path.join(REPO_ROOT, "cache", "picks.json")
PROSP_CACHE   = os.path.join(REPO_ROOT, "cache", "prospects.json")
CONS_CACHE    = os.path.join(REPO_ROOT, "cache", "consensus.json")
SLEEPER_CACHE = os.path.join(REPO_ROOT, "cache", "sleeper.json")
OUTPUT_FILE   = os.path.join(REPO_ROOT, "site", "rookies.html")


def _norm_name(text):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", "", text.lower())).strip()


def _load_rostered_norm_names(sleeper_data):
    """Return a set of normalized player names from all Sleeper rosters."""
    if not sleeper_data:
        return set()
    rosters = sleeper_data.get("rosters", {})
    player_meta = sleeper_data.get("player_metadata", {})
    names = set()
    for roster in rosters.values():
        for pid in roster.get("players", []):
            meta = player_meta.get(str(pid), {})
            full_name = meta.get("full_name", "")
            if full_name:
                names.add(_norm_name(full_name))
    return names


def _load_json(path):
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _fmt_pct(v):
    if v is None:
        return "--"
    try:
        return f"{float(v):.0%}"
    except (TypeError, ValueError):
        return "--"


def _fmt_val(v):
    return "--" if v is None else str(v)


# --- Rising Free Agents ---

def _render_usage(data):
    if data is None:
        return missing_section("rookie usage")
    last_updated = data.get("last_updated")
    data_note = data.get("data_note", "")
    banner = stale_banner("Usage", last_updated)
    players = data.get("players", [])

    if data_note and "no regular-season" in data_note.lower():
        note_html = f'<div class="banner-warn">&#128203; {escape(data_note)}</div>\n'
        return banner + note_html + '<p class="banner-missing">Usage data will populate once the regular season begins.</p>\n'

    if not players:
        return banner + missing_section("rookie usage")

    rising_fa = [p for p in players if p.get("trajectory") == "rising" and not p.get("rostered")]
    if not rising_fa:
        return banner + '<p class="banner-missing">No rising free-agent rookies found this week.</p>\n'

    rising_fa.sort(key=lambda p: p.get("last_snap_pct", 0) or 0, reverse=True)

    rows = []
    for p in rising_fa:
        name = escape(p.get("full_name") or p.get("name") or "")
        pos  = escape(p.get("position", ""))
        snap = _fmt_pct(p.get("last_snap_pct"))
        tgt  = _fmt_pct(p.get("last_target_share"))
        college = escape(p.get("college") or "--")
        note = escape(p.get("note") or "")
        rows.append(
            f"<tr><td>{name}</td><td>{pos}</td><td>{snap}</td>"
            f"<td>{tgt}</td><td>{college}</td><td>{note}</td></tr>"
        )

    ts_str = last_updated[:19].replace("T", " ") + " UTC" if last_updated else ""
    footer = f'<div class="section-meta">Source: nflverse &middot; Last synced: {ts_str}</div>' if ts_str else ""

    table = (
        '<div class="table-wrapper">'
        '<table><thead><tr>'
        "<th>Player</th><th>Pos</th><th>Snap%</th>"
        "<th>Target%</th><th>College</th><th>Note</th>"
        "</tr></thead><tbody>"
        + "\n".join(rows)
        + "</tbody></table></div>"
    )
    return banner + table + "\n" + footer


# --- Pick Tracker ---

def _resolve_our_name(picks_data):
    our_roster_id = picks_data.get("our_roster_id")
    if our_roster_id is None:
        return None
    sleeper = _load_json(SLEEPER_CACHE)
    if not sleeper:
        return None
    rosters = sleeper.get("rosters", {})
    user_map = sleeper.get("user_map", {})
    for user_id, roster in rosters.items():
        if roster.get("roster_id") == our_roster_id:
            return user_map.get(user_id)
    return None


def _pick_label(pick):
    return pick.get("label") or f"{pick['year']} Round {pick['round']}"


def _render_picks(data):
    if data is None:
        return missing_section("pick tracker")
    picks = data.get("picks", [])
    last_updated = data.get("last_updated")
    banner = stale_banner("Picks", last_updated)
    if not picks:
        return banner + missing_section("pick tracker")

    our_name = _resolve_our_name(data)
    ts_str = last_updated[:19].replace("T", " ") + " UTC" if last_updated else ""
    footer = f'<div class="section-meta">Source: Sleeper + KTC &middot; Last synced: {ts_str}</div>' if ts_str else ""

    sections = []

    # Our team section
    if our_name:
        our_picks = sorted(
            [p for p in picks if p.get("current_owner") == our_name],
            key=lambda p: (p["year"], p["round"]),
        )
        rows = []
        for p in our_picks:
            flag = "[?]" if p.get("uncertain") else ""
            prov = escape(p.get("provenance") or "")
            rows.append(
                f"<tr><td><span class='badge-our-pick'>{escape(_pick_label(p))}</span></td>"
                f"<td>{p.get('value', 'N/A')}</td><td>{prov}</td><td>{escape(flag)}</td></tr>"
            )
        if not rows:
            rows.append("<tr><td colspan='4'>No future picks</td></tr>")
        our_table = (
            f'<h3>Our Team ({escape(our_name)})</h3>'
            '<div class="table-wrapper"><table><thead><tr>'
            "<th>Pick</th><th>KTC Value</th><th>Provenance</th><th>Flag</th>"
            "</tr></thead><tbody>"
            + "\n".join(rows)
            + "</tbody></table></div>"
        )
        sections.append(our_table)

    # Full league section
    sorted_picks = sorted(picks, key=lambda p: (p["year"], p["round"], p.get("original_owner", "")))
    rows = []
    for p in sorted_picks:
        owner = escape(p.get("current_owner") or "")
        is_ours = our_name and owner == our_name
        owner_cell = f'<span class="badge-our-pick">{owner}</span>' if is_ours else owner
        flag = "[?]" if p.get("uncertain") else ""
        prov = escape(p.get("provenance") or "")
        rows.append(
            f"<tr><td>{escape(_pick_label(p))}</td><td>{owner_cell}</td>"
            f"<td>{p.get('value', 'N/A')}</td><td>{prov}</td><td>{escape(flag)}</td></tr>"
        )
    full_table = (
        '<h3>Full League</h3>'
        '<div class="table-wrapper"><table><thead><tr>'
        "<th>Pick</th><th>Owner</th><th>KTC Value</th><th>Provenance</th><th>Flag</th>"
        "</tr></thead><tbody>"
        + "\n".join(rows)
        + "</tbody></table></div>"
    )
    sections.append(full_table)

    return banner + "\n".join(sections) + "\n" + footer


# --- Prospect Board ---

def _render_prospects(prosp_data, cons_data, rostered_names):
    if prosp_data is None and cons_data is None:
        return missing_section("prospect board")

    last_updated = None
    banner = ""
    if prosp_data:
        last_updated = prosp_data.get("last_updated")
        banner = stale_banner("Prospects", last_updated)

    # Build consensus rank lookup by normalized name
    cons_lookup = {}
    if cons_data:
        for entry in cons_data.get("board", []):
            key = _norm_name(entry.get("name", ""))
            cons_lookup[key] = entry.get("consensus_rank")

    prospects = prosp_data.get("prospects", []) if prosp_data else []
    board = cons_data.get("board", []) if cons_data else []
    if not prospects and not board:
        return banner + missing_section("prospect board")

    rows = []
    if prospects:
        unrostered = [p for p in prospects if _norm_name(p.get("player", "")) not in rostered_names]
        for p in unrostered:
            name = escape(p.get("player", ""))
            pos  = escape(p.get("position", ""))
            school = escape(p.get("team", ""))
            stat_rank = p.get("stat_rank", "--")
            cons_rank = cons_lookup.get(_norm_name(p.get("player", "")), "--")
            score = p.get("composite_score", "--")
            rows.append(
                f"<tr><td>{stat_rank}</td><td>{name}</td><td>{pos}</td>"
                f"<td>{school}</td><td>{cons_rank}</td><td>{score}</td></tr>"
            )
    else:
        unrostered = [p for p in board if _norm_name(p.get("name", "")) not in rostered_names]
        for p in unrostered:
            name = escape(p.get("name", ""))
            pos  = escape(p.get("position", ""))
            school = escape(p.get("school", ""))
            cons_rank = p.get("consensus_rank", "--")
            rows.append(
                f"<tr><td>{cons_rank}</td><td>{name}</td><td>{pos}</td>"
                f"<td>{school}</td><td>{cons_rank}</td><td>--</td></tr>"
            )

    ts_str = last_updated[:19].replace("T", " ") + " UTC" if last_updated else ""
    footer = f'<div class="section-meta">Source: CFBD &middot; Rostered players filtered out &middot; Last synced: {ts_str}</div>' if ts_str else ""

    if not rows:
        return banner + '<p class="banner-missing">All tracked prospects are already rostered in the league.</p>\n' + footer

    table = (
        '<div class="table-wrapper"><table><thead><tr>'
        "<th>Stat Rank</th><th>Player</th><th>Pos</th>"
        "<th>School</th><th>Consensus</th><th>Composite Score</th>"
        "</tr></thead><tbody>"
        + "\n".join(rows)
        + "</tbody></table></div>"
    )
    return banner + table + "\n" + footer


def main():
    usage_data  = _load_json(USAGE_CACHE)
    picks_data  = _load_json(PICKS_CACHE)
    prosp_data  = _load_json(PROSP_CACHE)
    cons_data   = _load_json(CONS_CACHE)
    sleeper_data = _load_json(SLEEPER_CACHE)

    rostered_names = _load_rostered_norm_names(sleeper_data)

    usage_html   = _render_usage(usage_data)
    picks_html   = _render_picks(picks_data)
    prosp_html   = _render_prospects(prosp_data, cons_data, rostered_names)

    body = f"""<h1 class="page-title">Rookies &amp; Picks</h1>

<div class="section-card">
  <h2>Rising Free Agents</h2>
  {usage_html}
</div>

<div class="section-card">
  <h2>Pick Tracker</h2>
  {picks_html}
</div>

<div class="section-card">
  <h2>Prospect Board</h2>
  {prosp_html}
</div>"""

    html = page_shell("Rookies & Picks", "rookies", body)
    _atomic_write(OUTPUT_FILE, html)
    print("site/rookies.html written.")


if __name__ == "__main__":
    main()
