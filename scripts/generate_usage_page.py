"""Read cache/usage.json and render site/usage.md."""

import json
import os
import re
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
USAGE_CACHE = os.path.join(REPO_ROOT, "cache", "usage.json")
SLEEPER_CACHE = os.path.join(REPO_ROOT, "cache", "sleeper.json")
PROSPECTS_CACHE = os.path.join(REPO_ROOT, "cache", "prospects.json")
CONSENSUS_CACHE = os.path.join(REPO_ROOT, "cache", "consensus.json")
NEWS_CACHE = os.path.join(REPO_ROOT, "cache", "news.json")
OUTPUT_FILE = os.path.join(REPO_ROOT, "site", "usage.md")

STALE_DAYS = 9
TRAJ_THRESHOLD = 5.0
INJURY_KEYWORDS = ["injured", " out", " ir", "questionable", "placed on ir"]


def _normalize(text):
    text = text.lower()
    text = re.sub(r"[^a-z0-9 ]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _classify_trajectory(values):
    """Classify trend from a list of weekly floats (may contain None)."""
    non_null = [v for v in values if v is not None]
    if len(non_null) < 2:
        return "insufficient data"
    if len(non_null) == 2:
        diff = non_null[-1] - non_null[0]
    else:
        last2 = non_null[-2:]
        prior = non_null[:-2]
        diff = (sum(last2) / len(last2)) - (sum(prior) / len(prior))
    if diff > TRAJ_THRESHOLD:
        return "rising"
    if diff < -TRAJ_THRESHOLD:
        return "falling"
    return "flat"


def _load_rostered_names(sleeper):
    """Return set of normalized names currently on any roster."""
    metadata = sleeper.get("player_metadata", {})
    rostered_ids = set()
    for uid, roster in sleeper.get("rosters", {}).items():
        for pid in (roster.get("players") or []):
            rostered_ids.add(str(pid))
    names = set()
    for pid in rostered_ids:
        meta = metadata.get(pid) or metadata.get(str(pid))
        if meta and meta.get("full_name"):
            names.add(_normalize(meta["full_name"]))
    return names


def _load_college_ranks():
    stat_rank = {}
    consensus_rank = {}
    if os.path.exists(PROSPECTS_CACHE):
        try:
            with open(PROSPECTS_CACHE, encoding="utf-8") as f:
                data = json.load(f)
            for i, p in enumerate(data.get("prospects", []), 1):
                norm = _normalize(p.get("name", ""))
                if norm:
                    stat_rank[norm] = i
        except Exception:
            pass
    if os.path.exists(CONSENSUS_CACHE):
        try:
            with open(CONSENSUS_CACHE, encoding="utf-8") as f:
                data = json.load(f)
            for entry in data.get("board", []):
                norm = _normalize(entry.get("name", ""))
                rank = entry.get("consensus_rank")
                if norm and rank is not None:
                    consensus_rank[norm] = rank
        except Exception:
            pass
    return stat_rank, consensus_rank


def _load_news_records():
    if not os.path.exists(NEWS_CACHE):
        return []
    try:
        with open(NEWS_CACHE, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("items", [])
    except Exception:
        return []


def _headline_week(published_str, season_start_date=None):
    """Parse RFC 2822 date string to a rough week number (1-indexed from Sept 1)."""
    try:
        dt = parsedate_to_datetime(published_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        # Use ISO week number as a proxy; good enough for same-week detection
        return dt.isocalendar()[1]
    except Exception:
        return None


def _injury_flag(norm_name, position, nfl_team, rising_week_iso, news_records):
    """
    Return a flag string if a same-week headline mentions injury to a teammate
    at the same position. Returns None if no correlation detected.
    """
    if not news_records or not nfl_team or rising_week_iso is None:
        return None

    for item in news_records:
        title = item.get("title", "")
        desc = item.get("description", "")
        headline = (title + " " + desc).lower()

        # Check injury keyword
        if not any(kw in headline for kw in INJURY_KEYWORDS):
            continue

        # Check same-week (compare ISO week number)
        pub = item.get("published", "")
        item_week = _headline_week(pub)
        if item_week != rising_week_iso:
            continue

        # Check team and position mention (heuristic: team abbreviation in headline)
        if nfl_team.lower() not in headline:
            continue

        # Don't flag the player themselves
        if norm_name in _normalize(headline):
            continue

        # Extract injured player name from title (first capitalized sequence)
        match = re.match(r"([A-Z][a-z]+ [A-Z][a-zA-Z'.-]+)", title)
        injured_name = match.group(1) if match else "teammate"
        return f"Possible opportunity: {injured_name} (injury reported same week)"

    return None


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


def _render_table(players_data):
    """Render a markdown table for a list of player records."""
    lines = []
    lines.append("| Player | Pos | Snap Trend | Target Trend | RZ Touches (last wk) | College Rank | Note |")
    lines.append("|--------|-----|------------|--------------|----------------------|--------------|------|")
    for p in players_data:
        rz = "N/A"
        if p["weeks"]:
            last_week = p["weeks"][-1]
            rz_val = last_week.get("rz_targets")
            rz = str(rz_val) if rz_val is not None else "N/A"

        college = ""
        if p.get("stat_rank"):
            college = f"stat #{p['stat_rank']}"
        if p.get("consensus_rank"):
            college = (college + f" / consensus #{p['consensus_rank']}").lstrip(" / ")

        note = p.get("injury_flag") or ""
        snap = p.get("snap_trend", "insufficient data")
        tgt = p.get("target_trend", "insufficient data")

        lines.append(
            f"| {p['name']} | {p['position']} | {snap} | {tgt} | {rz} | {college or 'N/A'} | {note} |"
        )
    return "\n".join(lines)


def main():
    # Load usage cache
    if not os.path.exists(USAGE_CACHE):
        _atomic_write(
            OUTPUT_FILE,
            "# Rookie Usage Tracker\n\n_No usage data available. Run `python scripts/sync_usage.py` first._\n"
        )
        print("site/usage.md written (no cache).")
        return

    with open(USAGE_CACHE, encoding="utf-8") as f:
        usage = json.load(f)

    players_raw = usage.get("players", {})
    data_note = usage.get("data_note")
    last_updated = usage.get("last_updated", "")

    lines = ["# Rookie Usage Tracker", ""]

    # Stale warning
    if last_updated:
        try:
            lu = datetime.fromisoformat(last_updated)
            if lu.tzinfo is None:
                lu = lu.replace(tzinfo=timezone.utc)
            if (datetime.now(timezone.utc) - lu) > timedelta(days=STALE_DAYS):
                lines.append(f"**Warning: usage data is stale (last updated: {last_updated[:10]})**")
                lines.append("")
        except ValueError:
            pass

    # Data note (preseason, off-season, etc.)
    if data_note:
        lines.append(f"**Data note: {data_note}**")
        lines.append("")

    if not players_raw:
        lines.append("_No rookies tracked yet. Data will populate once the regular season begins._")
        _atomic_write(OUTPUT_FILE, "\n".join(lines) + "\n")
        print("site/usage.md written (placeholder).")
        return

    # Load cross-reference data
    sleeper = {}
    if os.path.exists(SLEEPER_CACHE):
        with open(SLEEPER_CACHE, encoding="utf-8") as f:
            sleeper = json.load(f)
    rostered_names = _load_rostered_names(sleeper)
    stat_rank, consensus_rank = _load_college_ranks()
    news_records = _load_news_records()

    # Build enriched player records
    enriched = []
    for norm_name, pdata in players_raw.items():
        weeks = pdata.get("weeks", [])
        snap_values = [w.get("snap_pct") for w in weeks]
        tgt_values = [w.get("target_share") for w in weeks]
        snap_trend = _classify_trajectory(snap_values)
        tgt_trend = _classify_trajectory(tgt_values)
        is_free_agent = norm_name not in rostered_names
        is_rising = snap_trend == "rising" or tgt_trend == "rising"

        # Injury flag: use last week with rising data as context
        injury_flag = None
        if is_rising and weeks:
            last_w = weeks[-1]
            nfl_team = last_w.get("nfl_team")
            week_num = last_w.get("week")
            injury_flag = _injury_flag(norm_name, pdata.get("position", ""), nfl_team, week_num, news_records)

        enriched.append({
            "name": pdata.get("player_name", norm_name),
            "norm_name": norm_name,
            "position": pdata.get("position", "?"),
            "snap_trend": snap_trend,
            "target_trend": tgt_trend,
            "is_free_agent": is_free_agent,
            "is_rising": is_rising,
            "stat_rank": stat_rank.get(norm_name),
            "consensus_rank": consensus_rank.get(norm_name),
            "injury_flag": injury_flag,
            "weeks": weeks,
        })

    # Split and sort
    rising_fa = sorted(
        [p for p in enriched if p["is_free_agent"] and p["is_rising"]],
        key=lambda p: ([w.get("snap_pct") or 0 for w in p["weeks"]] or [0])[-1],
        reverse=True,
    )
    rostered = sorted(
        [p for p in enriched if not p["is_free_agent"]],
        key=lambda p: p["name"],
    )
    other_fa = sorted(
        [p for p in enriched if p["is_free_agent"] and not p["is_rising"]],
        key=lambda p: p["name"],
    )

    # Render sections
    lines.append("## Rising Free Agents")
    lines.append("")
    lines.append("_Free-agent rookies with rising snap or target share — primary waiver targets._")
    lines.append("")
    if rising_fa:
        lines.append(_render_table(rising_fa))
    else:
        lines.append("_No free-agent rookies with rising usage this week._")
    lines.append("")

    lines.append("## Rostered Rookies")
    lines.append("")
    if rostered:
        lines.append(_render_table(rostered))
    else:
        lines.append("_No tracked rookies are on a league roster._")
    lines.append("")

    if other_fa:
        lines.append("## Other Free Agents")
        lines.append("")
        lines.append(_render_table(other_fa))
        lines.append("")

    lines.append(f"_Last updated: {last_updated[:19].replace('T', ' ')} UTC_")

    _atomic_write(OUTPUT_FILE, "\n".join(lines) + "\n")
    print(f"site/usage.md written ({len(enriched)} rookies).")


if __name__ == "__main__":
    main()
