## Why

Priority feature: **#4 — Roster/news sync** (foundational dependency for #2 trade analysis and #3 rookie tracker).

The hub has no live data yet. Without a reliable pipeline that pulls our league's current rosters from Sleeper and surfaces only relevant player news, every downstream feature — trade analysis, the rookie tracker, and the decision log — must work from stale or manually entered data. This is the first feature to build because it unblocks everything else.

## What Changes

- New script `scripts/sync_sleeper.py` fetches our league's rosters, active matchups, and recent transactions from Sleeper's public API and writes structured JSON to `cache/sleeper.json`.
- New script `scripts/sync_news.py` fetches RotoWire's NFL RSS feed and filters items against an expanded player set — rostered players plus a second tier of non-rostered players (league-wide trending adds, current-draft-class rookies, and a manually configured watchlist) — writing filtered results to `cache/news.json` with each item tagged by which tier(s) matched.
- Both scripts write a `last_updated` ISO timestamp into their output and fall back to the existing cache file if the upstream source fails or times out.
- New GitHub Actions workflow `.github/workflows/sync.yml` runs both scripts on a schedule (e.g., every 6 hours during the season).
- `requirements.txt` pinned and committed with all new dependencies.

## Capabilities

### New Capabilities

- `sleeper-sync`: Fetch roster, matchup, transaction, trending-adds, and player-metadata data from Sleeper's public REST API; write to `cache/sleeper.json` with graceful stale fallback.
- `news-filter`: Fetch RotoWire NFL RSS; filter items against an expanded player set (rostered + trending + rookie + watchlist tiers); tag each item with matched category; write to `cache/news.json` with graceful stale fallback.

### Modified Capabilities

*(none — no existing spec-level behavior changes)*

## Impact

- **New files**: `scripts/sync_sleeper.py`, `scripts/sync_news.py`, `.github/workflows/sync.yml`, `cache/.gitkeep`, `config.yaml` (watchlist)
- **Dependencies**: `requests`, `feedparser`, `PyYAML` (pinned in `requirements.txt`)
- **APIs**: Sleeper public REST API (no key required) — adds two new endpoints: trending-adds and player metadata. RotoWire RSS (public, free, no auth). No new data sources introduced.
- **Free-tier API implications**: All sources remain unauthenticated and free. The Sleeper player-metadata endpoint (`/v1/players/nfl`) returns a large payload (~2 MB); it is fetched once per scheduled run (every 6 hours), well within reasonable use. Trending-adds endpoint is lightweight.

## Non-goals

- No player stats, dynasty rankings, or trade value lookups — that is the trade analysis engine (priority #2).
- No college/prospect data — that belongs to the rookie asset tracker (priority #3).
- No HTML/static-site output — this script only produces JSON cache files.
- No per-user or real-time fetching — runs only on the GitHub Actions schedule.
