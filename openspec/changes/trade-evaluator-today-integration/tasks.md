## 1. Refactor analyze_trade.py

- [x] 1.1 Extract an `analyze_trade_assets(owner_a, assets_a, owner_b, assets_b, ktc, sleeper, team_mode)` function from the existing `compute_totals()` and `redundancy_flags()` calls in `analyze_trade.py`; it should return a dict with keys `raw_a`, `raw_b`, `adj_a`, `adj_b`, `verdict` (the verdict string), and `flags` (combined list); update `main()` to call it instead of the inline logic — no change to CLI prompts, printed output, or `write_decision_log()` behavior
- [x] 1.2 Smoke-test: run `python scripts/analyze_trade.py` interactively and confirm prompts and output are unchanged; also confirm `from analyze_trade import analyze_trade_assets` succeeds in a Python shell without errors

## 2. Batch Analysis Script

- [x] 2.1 Create `scripts/batch_analyze_trades.py`: load `data/decisions.json` and `cache/ktc.json`; if either is missing write a placeholder `cache/trade_analysis.json` (empty `results`, descriptive `data_note`, `last_updated` timestamp) and exit 0; otherwise filter entries to `type=trade`
- [x] 2.2 Implement description parser: regex `^(?P<owner_a>.+?) sends (?P<assets_a>.+?); (?P<owner_b>.+?) sends (?P<assets_b>.+)$`; comma-split each asset list; normalize each name with the same `_normalize_name` logic as `analyze_trade.py`; attempt exact `name_key` match against KTC players list then picks list; on miss, attempt substring match against `name_key`; collect unresolved names as `parse_flags`
- [x] 2.3 For each parsed trade, call `analyze_trade_assets()` imported from `analyze_trade`; if the description cannot be parsed at all (regex fails), record a `parse_flags` entry and skip computation for that ID; write a result entry with whatever partial data is available
- [x] 2.4 Load `config.yaml` for `team_mode`; load `cache/sleeper.json` for redundancy checks (pass to `analyze_trade_assets`); write completed `results` dict atomically to `cache/trade_analysis.json` with `last_updated` ISO timestamp and `data_note: "ok"`
- [x] 2.5 Smoke-test: run `python scripts/batch_analyze_trades.py`; inspect `cache/trade_analysis.json`; confirm the existing test trade entry ("Send Malik Nabers for a 1st") produces a result with `raw_a`, `raw_b`, `verdict`, and any `parse_flags` for unresolved names

## 3. Today Page Integration

- [x] 3.1 In `generate_today_page.py`, load `cache/trade_analysis.json` at startup (silent no-op if file absent or unparseable); build an in-memory `analysis_by_id` dict keyed by decision ID
- [x] 3.2 In `_render_decisions()`, for each entry with `type=trade`, check `analysis_by_id.get(entry["id"])`; if present, render an inline `<details>` block beneath the vote row with `<summary>` showing the verdict string and inner content showing: Side A owner + assets + raw value, Side B owner + assets + raw value, adjusted values for each side, and any flags or parse_flags; if absent, render the vote row as usual with no additional markup
- [x] 3.3 Add CSS for the analysis detail block to `site/static/style.css`: `.trade-analysis` styles (indented, muted border-left, smaller font), `details > summary` cursor pointer, and any value-highlight spans
- [x] 3.4 Smoke-test: run `python scripts/generate_today_page.py`; open `site/index.html`; confirm the test trade entry shows a `<details>` block with verdict and value breakdown; confirm a non-trade entry has no `<details>` block

## 4. GitHub Actions

- [x] 4.1 In `publish.yml`, add a "Batch analyze trades" step (`python scripts/batch_analyze_trades.py`) after the "Resolve decisions" step and before "Generate today page"; add `cache/trade_analysis.json` to the `git add` line in the commit step
- [x] 4.2 Verify no new packages are needed (`batch_analyze_trades.py` uses only stdlib + `yaml` + imports from `analyze_trade.py` which already uses `yaml` — no lockfile change)
