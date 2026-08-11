"""Fetch nflverse weekly rookie usage data and write cache/usage.json."""

import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone

import yaml

REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
CONFIG_FILE = os.path.join(REPO_ROOT, "config.yaml")
SLEEPER_CACHE = os.path.join(REPO_ROOT, "cache", "sleeper.json")
OUTPUT_FILE = os.path.join(REPO_ROOT, "cache", "usage.json")

SKILL_POSITIONS = {"QB", "RB", "WR", "TE"}
ROOKIE_EXP_MAX = 1  # years_exp 0 or 1


def _normalize(text):
    text = text.lower()
    text = re.sub(r"[^a-z0-9 ]", "", text)
    return re.sub(r"\s+", " ", text).strip()


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


def _write_placeholder(season_type, data_note=None):
    note = data_note or f"{season_type} -- not representative"
    payload = {
        "season_type": season_type,
        "data_note": note,
        "players": [],
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }
    _atomic_write(OUTPUT_FILE, payload)


def _load_sleeper():
    if not os.path.exists(SLEEPER_CACHE):
        print("Error: cache/sleeper.json missing — run sync_sleeper.py first.", file=sys.stderr)
        sys.exit(1)
    with open(SLEEPER_CACHE, encoding="utf-8") as f:
        return json.load(f)


def _build_rookie_scope(sleeper):
    """Return dict: normalized_name -> {player_id, full_name, position, years_exp}."""
    metadata = sleeper.get("player_metadata", {})
    scope = {}
    for pid, meta in metadata.items():
        pos = meta.get("position", "")
        if pos not in SKILL_POSITIONS:
            continue
        try:
            exp = int(meta.get("years_exp", 99))
        except (TypeError, ValueError):
            continue
        if exp > ROOKIE_EXP_MAX:
            continue
        full_name = meta.get("full_name", "")
        if not full_name:
            continue
        norm = _normalize(full_name)
        scope[norm] = {
            "player_id": pid,
            "full_name": full_name,
            "position": pos,
            "years_exp": exp,
        }
    return scope


def _safe_float(val):
    """Return float or None; treat NaN as None."""
    if val is None:
        return None
    try:
        f = float(val)
        import math
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None


def _safe_int(val):
    """Return int or None."""
    if val is None:
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def _fetch_usage(season, rookie_scope):
    """Fetch nflverse weekly roster data and pivot to per-player weekly records."""
    try:
        import nfl_data_py as nfl
    except ImportError:
        print("Error: nfl_data_py not installed. Run: pip install -r requirements.txt", file=sys.stderr)
        sys.exit(1)

    print(f"Fetching nflverse weekly rosters for {season}...")
    try:
        df = nfl.import_weekly_rosters(years=[season])
    except Exception as exc:
        print(f"Error fetching nflverse data: {exc}", file=sys.stderr)
        sys.exit(1)

    if df is None or df.empty:
        print("nflverse returned empty data — season may not have started.", file=sys.stderr)
        return {}

    # Normalise player_name column for matching
    name_col = "player_name" if "player_name" in df.columns else None
    if name_col is None:
        print("Error: expected 'player_name' column not found in nflverse data.", file=sys.stderr)
        print(f"Available columns: {list(df.columns)}", file=sys.stderr)
        sys.exit(1)

    df["_norm_name"] = df[name_col].astype(str).apply(_normalize)

    # Filter to rookies only
    df_rookies = df[df["_norm_name"].isin(rookie_scope)]
    if df_rookies.empty:
        print("No rookie matches found in nflverse data this week.")
        return {}

    # Map column names — nflverse uses these field names (may vary by version)
    FIELD_MAP = {
        "snap_pct": ["snap_pct", "offense_pct"],
        "target_share": ["target_share", "tgt_sh"],
        "route_participation": ["route_participation", "routes_run_pct"],
        "rz_targets": ["rz_tgt_sh", "rz_targets", "ez_tgt_sh"],
    }

    def _pick_col(aliases):
        for a in aliases:
            if a in df.columns:
                return a
        return None

    col_snap = _pick_col(FIELD_MAP["snap_pct"])
    col_tgt = _pick_col(FIELD_MAP["target_share"])
    col_route = _pick_col(FIELD_MAP["route_participation"])
    col_rz = _pick_col(FIELD_MAP["rz_targets"])

    players = {}
    for norm_name, group in df_rookies.groupby("_norm_name"):
        meta = rookie_scope[norm_name]
        weeks = []
        for _, row in group.sort_values("week").iterrows():
            week_rec = {
                "week": _safe_int(row.get("week")),
                "snap_pct": _safe_float(row.get(col_snap) if col_snap else None),
                "target_share": _safe_float(row.get(col_tgt) if col_tgt else None),
                "route_participation": _safe_float(row.get(col_route) if col_route else None),
                "rz_targets": _safe_int(row.get(col_rz) if col_rz else None),
                "nfl_team": str(row.get("team", "")) or None,
            }
            weeks.append(week_rec)
        players[norm_name] = {
            "player_name": meta["full_name"],
            "position": meta["position"],
            "years_exp": meta["years_exp"],
            "sleeper_id": meta["player_id"],
            "weeks": weeks,
        }

    return players


def main():
    with open(CONFIG_FILE, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    sleeper = _load_sleeper()
    nfl_state = sleeper.get("nfl_state") or {}
    season_type = nfl_state.get("season_type", "unknown")
    season = nfl_state.get("season")

    if season_type != "regular":
        print(f"season_type={season_type!r} -- skipping usage fetch")
        note = "preseason -- not representative" if season_type == "pre" else f"{season_type} -- no regular-season data"
        _write_placeholder(season_type, note)
        return

    if not season:
        season = datetime.now(timezone.utc).year
        print(f"Warning: nfl_state.season missing, defaulting to {season}")

    season = int(season)
    print(f"Regular season detected: season={season}")

    rookie_scope = _build_rookie_scope(sleeper)
    print(f"Rookie scope: {len(rookie_scope)} skill-position players with years_exp <= {ROOKIE_EXP_MAX}")

    players = _fetch_usage(season, rookie_scope)

    payload = {
        "season_type": season_type,
        "season": season,
        "players": players,
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }
    _atomic_write(OUTPUT_FILE, payload)
    print(f"sync_usage: {len(players)} rookies written to cache/usage.json")


if __name__ == "__main__":
    main()
