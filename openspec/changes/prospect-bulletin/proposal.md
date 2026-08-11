## Why

The rookie asset tracker needs a prospect-facing view. Pick values alone (from pick-tracker) don't tell owners which players those picks might land — a weekly bulletin closes that gap by surfacing the top dynasty-relevant college players, blending stat-based production signals with public consensus rankings.

## What Changes

- New script `scripts/sync_prospects.py` fetches current-season college stats from the CFBD API and computes a dynasty-relevant composite score per player.
- New script `scripts/sync_consensus.py` pulls or reads a public consensus big board; initially a manually-updated JSON reference if no reliably scriptable free source exists.
- New script `scripts/generate_bulletin.py` merges both signals, ranks top 15–20 names, flags divergence between stat rank and consensus rank, and writes `site/bulletin.md`.
- New GitHub Actions workflow `prospect.yml` runs Monday mornings (after college football weekends) on a weekly cron.
- `cache/prospects.json` and `cache/consensus.json` committed as stale-fallback cache files; `site/bulletin.md` committed as the rendered page.

## Capabilities

### New Capabilities

- `prospect-stats`: Fetch and score college player production from CFBD API — yards, TDs, target share, efficiency, age-adjusted dynasty heuristic composite score
- `prospect-consensus`: Store and serve a public consensus big board as a rankable list; live pull if feasible, manually-updated JSON fallback otherwise
- `prospect-bulletin`: Merge stat rank + consensus rank into a weekly bulletin page showing top 15–20 names with divergence flags

### Modified Capabilities

_(none — no existing spec-level behavior changes)_

## Impact

- New dependency: `cfbd` Python client or direct CFBD REST calls (free tier, 1,000 calls/month — weekly run uses ~5–10 calls)
- New GitHub Actions workflow (separate from `sync.yml`; distinct Monday schedule)
- No changes to existing scripts, caches, or workflows
- `site/bulletin.md` sits alongside `site/picks.md` on the static site

## Non-goals

- Full scouting profiles or narrative write-ups (that belongs in a future LLM-generated feature)
- Real-time or per-user refresh
- NFL usage stats (nflverse) — this bulletin covers college players only
- Automatic cross-referencing with pick-tracker pick ownership (future enhancement; layout compatibility is sufficient for now)
