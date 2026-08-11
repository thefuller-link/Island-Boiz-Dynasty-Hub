## Why

Dynasty success is built on draft capital — but right now we have no single place to see which future picks each team owns, what they're worth, or which ones changed hands in trades. Building a pick tracker surfaces this at a glance and becomes the foundation for the rest of the rookie asset tracker group.

## What Changes

- New script `scripts/sync_picks.py` derives future pick ownership by replaying Sleeper transaction history, combines with `cache/ktc.json` for live values, and writes `cache/picks.json`
- New file `data/pick_overrides.json` allows manual correction for picks Sleeper can't cleanly expose (conditionals, pending complications)
- New script `scripts/generate_picks_page.py` reads `cache/picks.json` and renders `site/picks.md` — a per-team view and a full-league view of all future picks with values and provenance
- `sync.yml` gets a `Sync picks` step after the existing KTC sync; `cache/picks.json` added to the commit step
- `publish.yml` (or a new workflow) regenerates `site/picks.md` on push

## Capabilities

### New Capabilities

- `pick-sync`: Derive future pick ownership from Sleeper transactions, merge pick-value data from KTC cache, flag uncertain picks, write `cache/picks.json`
- `picks-page`: Read `cache/picks.json` and render `site/picks.md` with per-team and full-league views

### Modified Capabilities

_(none)_

## Impact

- Reads `cache/sleeper.json` (user_map, rosters, transactions from roster-news-sync)
- Reads `cache/ktc.json` (pick values from trade-analysis-engine)
- Reads `data/pick_overrides.json` (new manual file, committed to repo)
- Writes `cache/picks.json`
- Writes `site/picks.md`
- No new Python packages needed (requests + yaml already in requirements.txt)
- Sleeper API free tier: transaction history endpoint is public/unauthenticated, same as other calls; no additional quota pressure
- Priority: #3 (rookie asset tracker — foundational piece); depends on roster-news-sync and trade-analysis-engine (both applied)

## Non-goals

- Real-time conditional pick resolution (conditionals are flagged, not resolved automatically)
- Tracking DEVY or IDP picks
- Prospect scouting or college stats (separate prospect-bulletin change)
- Usage/snap-count tracking (separate usage-tracker change)
- Historical pick value charts
