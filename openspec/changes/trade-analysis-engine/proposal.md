## Why

Trading in a co-owned dynasty league requires shared objective criteria — right now we evaluate trades purely by feel, which leads to disagreement and post-trade regret. A quantitative engine using publicly-sourced dynasty values gives all three owners a neutral baseline to anchor trade discussions, independent of subjective bias.

## What Changes

- New script `scripts/sync_ktc.py` fetches KeepTradeCut dynasty values (players + exact picks) and caches to `cache/ktc.json`
- New script `scripts/analyze_trade.py` reads `cache/ktc.json` and `cache/sleeper.json`, accepts a proposed trade as input, calculates value totals per side, applies context-aware adjustments, and prints a structured verdict
- `config.yaml` gains a `team_mode` key per owner (contending / retooling / rebuilding) used for pick-weight adjustments
- Optional integration: after generating a verdict, offer to pre-fill a `log_decision.py` new-entry so analysis and owner responses stay in one record
- New GitHub Actions workflow step (or separate workflow) to run `sync_ktc.py` on schedule alongside existing cache syncs

## Capabilities

### New Capabilities

- `ktc-sync`: Fetch KeepTradeCut dynasty trade values (players + picks), cache as `cache/ktc.json`; expose last-updated timestamp for staleness detection
- `trade-evaluator`: Accept a proposed trade (sides + assets), compute value totals, apply rebuild/contend pick-weight adjustments, flag positional redundancy from roster data, output a structured verdict

### Modified Capabilities

_(none — no existing specs change behavior)_

## Impact

- New dependency: `requests` already in requirements.txt; no new packages needed if KTC exposes a parseable endpoint (see notes in design)
- Reads `cache/sleeper.json` (from roster-news-sync, already applied)
- Writes `cache/ktc.json`
- Reads `config.yaml` for `team_mode` per owner
- No LLM call in this feature — pure math/rules
- Priority: #3 (trade analysis engine) in the roadmap
- Free-tier note: KeepTradeCut does not publish a documented public API; values are fetched from their public-facing data endpoint (no auth, no rate-limit documentation). Script should handle HTTP errors gracefully and fall back to stale cache.

## Non-goals

- LLM-generated narrative commentary (planned separately)
- Historical value tracking or trend charting
- Automatic trade submission to Sleeper
- UI/interactive web form (verdict is CLI output for now)
