"""Read cache/news.json + cache/sleeper.json + cache/ktc.json + data/decisions.json and write site/index.html."""

import json
import os
import re
from email.utils import parsedate_to_datetime
from html import escape

import sys
sys.path.insert(0, os.path.dirname(__file__))
from html_utils import page_shell, stale_banner, missing_section, _atomic_write

REPO_ROOT           = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
NEWS_CACHE          = os.path.join(REPO_ROOT, "cache", "news.json")
SLEEPER_CACHE       = os.path.join(REPO_ROOT, "cache", "sleeper.json")
KTC_CACHE           = os.path.join(REPO_ROOT, "cache", "ktc.json")
TRADE_ANALYSIS      = os.path.join(REPO_ROOT, "cache", "trade_analysis.json")
DECISIONS           = os.path.join(REPO_ROOT, "data", "decisions.json")
OUTPUT_FILE         = os.path.join(REPO_ROOT, "site", "index.html")

OUR_ROSTER_ID  = 2

POS_ORDER = ["QB", "RB", "WR", "TE", "K", "DEF"]

RESOLUTION_LABEL = {
    "approved":              "Approved",
    "vetoed":                "Vetoed",
    "abstained-to-majority": "Approved (abstain-to-majority)",
    "auto-approved":         "Auto-approved",
    "pending":               "Pending",
}
RESOLUTION_BADGE = {
    "approved":              "approved",
    "vetoed":                "vetoed",
    "abstained-to-majority": "approved",
    "auto-approved":         "approved",
    "pending":               "pending",
}

SLOT_LABEL = {
    "starter": "S",
    "bench":   "BN",
    "taxi":    "TX",
    "ir":      "IR",
}


def _norm_name(text):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", "", text.lower())).strip()


def _load_json(path):
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


# --- Our Roster ---

def _render_roster(sleeper_data, ktc_data):
    if sleeper_data is None:
        return missing_section("roster")

    banner = stale_banner("Roster", sleeper_data.get("last_updated"))
    rosters  = sleeper_data.get("rosters", {})
    meta     = sleeper_data.get("player_metadata", {})
    our_roster = next((r for r in rosters.values() if r.get("roster_id") == OUR_ROSTER_ID), None)
    if not our_roster:
        return banner + missing_section("roster")

    starters = set(our_roster.get("starters", []) or [])
    taxi     = set(our_roster.get("taxi", []) or [])
    reserve  = set(our_roster.get("reserve", []) or [])
    all_ids  = our_roster.get("players", []) or []

    ktc_lookup = {}
    if ktc_data:
        for p in ktc_data.get("players", []):
            ktc_lookup[p.get("name_key", "")] = p.get("value")

    # Build player list
    players = []
    for pid in all_ids:
        m = meta.get(str(pid), {})
        name = m.get("full_name", f"player_{pid}")
        pos  = m.get("position", "?")
        val  = ktc_lookup.get(_norm_name(name))
        if pid in starters:
            slot = "starter"
        elif pid in taxi:
            slot = "taxi"
        elif pid in reserve:
            slot = "ir"
        else:
            slot = "bench"
        players.append({"name": name, "pos": pos, "value": val, "slot": slot})

    # Group by position in display order, then sort each group by value desc
    groups = {}
    for p in players:
        pos = p["pos"] if p["pos"] in POS_ORDER else "?"
        groups.setdefault(pos, []).append(p)
    for pos in groups:
        groups[pos].sort(key=lambda x: x["value"] or 0, reverse=True)

    rows_html = []
    for pos in POS_ORDER + ["?"]:
        if pos not in groups:
            continue
        for p in groups[pos]:
            val_str = str(p["value"]) if p["value"] is not None else "--"
            slot_badge = SLOT_LABEL.get(p["slot"], p["slot"])
            slot_cls = f'slot-{p["slot"]}'
            rows_html.append(
                f'<tr>'
                f'<td class="pos-cell">{escape(p["pos"])}</td>'
                f'<td>{escape(p["name"])}</td>'
                f'<td>{val_str}</td>'
                f'<td><span class="slot-badge {slot_cls}">{slot_badge}</span></td>'
                f'</tr>'
            )

    ts_str = sleeper_data.get("last_updated", "")[:19].replace("T", " ") + " UTC"
    ktc_ts = ktc_data.get("last_updated", "")[:19].replace("T", " ") + " UTC" if ktc_data else ""
    footer = f'<div class="section-meta">Roster: Sleeper &middot; Values: KTC &middot; Last synced: {ts_str}</div>'

    table = (
        '<div class="table-wrapper"><table><thead><tr>'
        '<th>Pos</th><th>Player</th><th>KTC Value</th><th>Slot</th>'
        '</tr></thead><tbody>'
        + "\n".join(rows_html)
        + '</tbody></table></div>'
    )
    return banner + table + "\n" + footer


# --- News ---

def _parse_published(pub_str):
    if not pub_str:
        return ""
    try:
        return parsedate_to_datetime(pub_str).isoformat()
    except Exception:
        pass
    return pub_str


def _render_news(data):
    if data is None:
        return missing_section("news")
    items = data.get("items", [])
    last_updated = data.get("last_updated")
    banner = stale_banner("News", last_updated)
    if not items:
        return banner + missing_section("news")

    # Rostered items first, then others; within each group reverse-chrono
    def sort_key(x):
        is_rostered = "rostered" in x.get("categories", [])
        return (0 if is_rostered else 1, _parse_published(x.get("published", "")))

    sorted_items = sorted(items, key=sort_key, reverse=False)
    # reverse the timestamp part: re-sort with rostered=0 desc timestamp
    rostered = sorted(
        [x for x in items if "rostered" in x.get("categories", [])],
        key=lambda x: _parse_published(x.get("published", "")), reverse=True
    )
    other = sorted(
        [x for x in items if "rostered" not in x.get("categories", [])],
        key=lambda x: _parse_published(x.get("published", "")), reverse=True
    )
    sorted_items = rostered + other

    rows = []
    for item in sorted_items:
        title = escape(item.get("title", ""))
        link  = item.get("link", "")
        pub   = escape(item.get("published", ""))
        cats  = item.get("categories", [])
        is_rostered = "rostered" in cats
        other_cats = [c for c in cats if c != "rostered"]
        tag_parts = (["our player"] if is_rostered else []) + [escape(c) for c in other_cats]
        tag = " &middot; ".join(tag_parts)
        headline = f'<a href="{escape(link)}" target="_blank" rel="noopener">{title}</a>' if link else title
        rostered_cls = ' rostered-item' if is_rostered else ''
        meta_parts = [p for p in [pub, tag] if p]
        meta = " &middot; ".join(meta_parts)
        rows.append(
            f'<div class="news-item{rostered_cls}">'
            f'<div class="headline">{headline}</div>'
            f'<div class="meta">{meta}</div>'
            f'</div>'
        )
    ts_str = last_updated[:19].replace("T", " ") + " UTC" if last_updated else ""
    footer = f'<div class="section-meta">Source: RotoWire &middot; Last synced: {ts_str}</div>' if ts_str else ""
    return banner + "\n".join(rows) + "\n" + footer


# --- Decisions ---

def _render_trade_analysis(a):
    """Render a <details> block for a trade analysis result dict."""
    verdict = escape(a.get("verdict") or "analysis unavailable")
    owner_a = escape(a.get("owner_a") or "")
    owner_b = escape(a.get("owner_b") or "")

    def asset_list(assets):
        if not assets:
            return "<em>none resolved</em>"
        return escape(", ".join(x.get("name", "") for x in assets))

    assets_a_html = asset_list(a.get("assets_a", []))
    assets_b_html = asset_list(a.get("assets_b", []))
    raw_a  = a.get("raw_a")
    raw_b  = a.get("raw_b")
    adj_a  = a.get("adj_a")
    adj_b  = a.get("adj_b")

    val_a = f"{raw_a}" if raw_a is not None else "--"
    val_b = f"{raw_b}" if raw_b is not None else "--"
    adj_a_s = f"{adj_a:.0f}" if adj_a is not None else "--"
    adj_b_s = f"{adj_b:.0f}" if adj_b is not None else "--"

    all_flags = (a.get("flags") or []) + (a.get("parse_flags") or [])
    flags_html = ""
    if all_flags:
        items = "".join(f"<li>{escape(f)}</li>" for f in all_flags)
        flags_html = f'<ul class="trade-flags">{items}</ul>'

    body = (
        f'<table class="trade-values">'
        f'<tr><th></th><th>{owner_a} sends</th><th>{owner_b} sends</th></tr>'
        f'<tr><td>Assets</td><td>{assets_a_html}</td><td>{assets_b_html}</td></tr>'
        f'<tr><td>Raw KTC</td><td>{val_a}</td><td>{val_b}</td></tr>'
        f'<tr><td>Adjusted</td><td>{adj_a_s}</td><td>{adj_b_s}</td></tr>'
        f'</table>'
        f'{flags_html}'
    )
    return (
        f'<details class="trade-analysis">'
        f'<summary>Value analysis: {verdict}</summary>'
        f'<div class="trade-analysis-body">{body}</div>'
        f'</details>'
    )


def _render_decisions(data, analysis_by_id=None):
    if data is None:
        return missing_section("decisions")
    if not data:
        return missing_section("decisions")
    if analysis_by_id is None:
        analysis_by_id = {}
    sorted_entries = sorted(data, key=lambda x: x.get("id", ""), reverse=True)
    rows = []
    for entry in sorted_entries:
        desc  = escape(entry.get("description", ""))
        etype = escape(entry.get("type", ""))
        date  = escape(entry.get("date", ""))
        proposer = escape(entry.get("proposer", ""))
        resolution = entry.get("resolution", "pending")
        if isinstance(resolution, dict):
            resolution = "pending"
        badge_cls = RESOLUTION_BADGE.get(resolution, "pending")
        label = RESOLUTION_LABEL.get(resolution, resolution.capitalize())
        reason = escape(entry.get("resolution_reason", "") or "")
        reason_html = f' <span class="meta">{reason}</span>' if reason else ""

        analysis_html = ""
        if entry.get("type") == "trade":
            analysis = analysis_by_id.get(entry.get("id", ""))
            if analysis:
                analysis_html = _render_trade_analysis(analysis)

        rows.append(
            f'<div class="decision-item">'
            f'<div class="desc">'
            f'<span class="status-badge badge-{badge_cls}">{label}</span>'
            f'{desc}{reason_html}'
            f'</div>'
            f'<div class="meta">{etype} &middot; {date} &middot; {proposer}</div>'
            f'{analysis_html}'
            f'</div>'
        )
    return "\n".join(rows)


def main():
    sleeper_data    = _load_json(SLEEPER_CACHE)
    ktc_data        = _load_json(KTC_CACHE)
    news_data       = _load_json(NEWS_CACHE)
    decisions_data  = _load_json(DECISIONS)
    trade_analysis  = _load_json(TRADE_ANALYSIS)

    analysis_by_id = {}
    if trade_analysis:
        analysis_by_id = trade_analysis.get("results", {})

    roster_html    = _render_roster(sleeper_data, ktc_data)
    news_html      = _render_news(news_data)
    decisions_html = _render_decisions(decisions_data, analysis_by_id)

    body = f"""<h1 class="page-title">Today</h1>

<div class="section-card">
  <h2>Our Roster</h2>
  {roster_html}
</div>

<div class="section-card">
  <h2>News</h2>
  {news_html}
</div>

<div class="section-card">
  <h2>Decisions &amp; Votes</h2>
  {decisions_html}
</div>"""

    html = page_shell("Today", "today", body)
    _atomic_write(OUTPUT_FILE, html)
    print("site/index.html written.")


if __name__ == "__main__":
    main()
