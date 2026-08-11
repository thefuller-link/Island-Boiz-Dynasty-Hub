## Why

The league needs a weekly signal for which rookie free agents are seeing real usage growth — rising snap share and target counts — so owners can make timely waiver claims before breakout games happen. Today that data lives in nflverse but requires manual lookup; this feature surfaces it automatically alongside the college-scouting context already in the hub.

## What Changes

- New `scripts/sync_usage.py`: fetches nflverse weekly participation data (snap counts, target share, route participation, red zone touches) for current-season rookies; writes `cache/usage.json`
- New `scripts/generate_usage_page.py`: reads `cache/usage.json`, cross-references `cache/sleeper.json` (roster membership), `cache/prospects.json` / `cache/consensus.json` (college profile), and `cache/news.json` (injury context); writes `site/usage.md`
- New `.github/workflows/usage.yml`: daily cron during active NFL season only; commits cache and page with `[skip ci]`

## Capabilities

### New Capabilities

- `usage-tracker`: Weekly rookie usage trends (snap %, target share, route participation, red zone touches) with trajectory labels (rising/flat/falling), roster-vs-free-agent classification, college cross-reference, and injury-correlation flags

### Modified Capabilities

_(none — no existing spec-level behavior changes)_

## Impact

- **New dependency**: nflverse public data via `nfl_data_py` PyPI package (free, no API key required; pulls from GitHub-hosted parquet files)
- **New cache file**: `cache/usage.json`
- **New site page**: `site/usage.md`
- **New workflow**: `.github/workflows/usage.yml` (daily, season-gated)
- **Cross-references** (read-only): `cache/sleeper.json`, `cache/news.json`, `cache/prospects.json`, `cache/consensus.json`
- Relates to priority feature **3 — Rookie asset tracker** (final piece alongside pick-tracker and prospect-bulletin)

## Non-goals

- No historical multi-season tracking — current season only
- No LLM narrative generation for this feature
- No per-player detail pages — single aggregated `site/usage.md`
- No preseason data analysis — script gates on `season_type == "regular"` or explicit config flag; preseason runs are logged and produce a placeholder page
- No veteran usage tracking — rookies only (`years_exp == 0` or `years_exp == 1` for first full season)
