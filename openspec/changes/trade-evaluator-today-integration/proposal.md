## Why

The site-shell Today page was scoped to omit trade value analysis because `analyze_trade.py` is an interactive CLI tool — but that reasoning was wrong. The computation layer (`compute_totals`, `redundancy_flags`) is already pure and callable without a TTY; only the prompting wrappers are interactive. The result is that the Today page shows vote outcomes (approved/vetoed) without showing whether the trade is actually fair, which was an explicit original requirement.

## What Changes

- New `scripts/batch_analyze_trades.py`: reads every `type=trade` entry in `data/decisions.json`, resolves asset names against `cache/ktc.json` (exact `name_key` match then fuzzy fallback), calls the existing `compute_totals()` and `redundancy_flags()` functions from `analyze_trade.py` without any TTY interaction, and writes results keyed by decision ID to `cache/trade_analysis.json`; unresolvable assets are recorded as a flag rather than causing a failure
- `analyze_trade.py` gains an importable `analyze_trade_assets(owner_a, assets_a, owner_b, assets_b, ktc, sleeper, team_mode)` function extracted from the existing inline computation, callable without `input()`; the existing interactive `main()` is updated to call it — no behavior change to the CLI
- `generate_today_page.py` updated to load `cache/trade_analysis.json` and, for each decision entry with `type=trade`, embed the KTC value breakdown and verdict directly beneath the vote status row; if no analysis entry exists for a given ID, the vote row renders as before without error
- `publish.yml` updated to run `batch_analyze_trades.py` before `generate_today_page.py`

## Capabilities

### New Capabilities

- `trade-batch-analysis`: Programmatic batch runner that applies trade-evaluator logic to all decision-log trades and writes results to a cache file, without requiring interactive input

### Modified Capabilities

- `trade-evaluator`: Refactored to expose importable computation functions (`analyze_trade_assets`) in addition to the existing interactive CLI entry point; no change to CLI behavior or output format
- `site-shell`: Today page now embeds per-trade KTC value analysis (raw values, adjusted values, verdict, flags) alongside the existing vote-status row for trade entries

## Impact

- **New files**: `scripts/batch_analyze_trades.py`, `cache/trade_analysis.json` (generated)
- **Modified scripts**: `scripts/analyze_trade.py` (extract importable function; CLI unchanged), `scripts/generate_today_page.py` (read trade_analysis.json, render inline), `.github/workflows/publish.yml` (add batch_analyze_trades.py step)
- **No new dependencies**: uses only stdlib + `yaml` + `json` (already in requirements.txt)
- **No new API calls**: reads only existing `cache/ktc.json` and `cache/sleeper.json`
- Relates to priority features: **#1 decision log**, **#2 trade analysis engine**

## Non-goals

- No re-architecture of `analyze_trade.py`'s interactive prompting — only extract computation to a callable function
- No changes to how `analyze_trade.py` writes to `decisions.json`; the batch runner only reads it
- No changes to the `decisions.json` schema — the batch runner parses descriptions as written
- No fuzzy matching UI or correction of unresolvable names; unresolved assets are flagged and skipped
