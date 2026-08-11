## Context

See proposal.md (Why). `analyze_trade.py`'s computation is already isolated: `compute_totals()` and `redundancy_flags()` are pure functions with no I/O. Only `prompt_owner()` and `prompt_assets()` use `input()`. The extraction to `analyze_trade_assets()` is a thin wrapper over existing logic with no algorithmic change.

Decision description format (written by `write_decision_log()`):
```
"{owner_a} sends {a1}, {a2}; {owner_b} sends {b1}, {b2}"
```
This is the only source of structured trade data in `decisions.json` — no separate `assets` field exists. The batch runner parses this string.

## Goals / Non-Goals

**Goals:**
- Extract `analyze_trade_assets()` from existing `analyze_trade.py` computation code with zero behavioral change to the CLI
- Parse trade descriptions to reconstruct asset lists, covering the common case (clean names matching KTC `name_key`)
- Write `cache/trade_analysis.json` following the same stale-fallback pattern as every other cache script
- Render inline analysis on the Today page without breaking entries that lack analysis

**Non-Goals:**
- No fuzzy/interactive correction of unresolvable names in batch mode — flag and move on
- No schema change to `decisions.json`
- No change to `analyze_trade.py` prompts, output format, or decision-log write behavior

## Decisions

### Decision: Extract `analyze_trade_assets()` in-place, not a separate module
The function stays in `analyze_trade.py` so the file remains self-contained and importable without a separate package structure. The batch runner does `from scripts.analyze_trade import analyze_trade_assets` (or adds `scripts/` to `sys.path` and imports directly, matching the pattern used by other scripts that import `html_utils`).

### Decision: Parse descriptions with a single regex, flag on failure
Pattern: `^(?P<owner_a>.+?) sends (?P<assets_a>.+?); (?P<owner_b>.+?) sends (?P<assets_b>.+)$`
Each asset list is comma-split and trimmed. Each name is normalized and matched against KTC `name_key` exactly, then by checking if the normalized name appears as a substring of any `name_key`. Unmatched names go into `parse_flags`; matched assets proceed to computation.

_Alternative considered:_ Store structured `assets_a`/`assets_b` in `decisions.json` at write time. Cleaner but changes the schema and requires modifying `write_decision_log()` — a broader change than this correction warrants.

### Decision: `trade_analysis.json` schema
```json
{
  "last_updated": "ISO-8601-UTC",
  "data_note": "ok | <reason if placeholder>",
  "results": {
    "<decision-id>": {
      "owner_a": "...", "owner_b": "...",
      "assets_a": [...], "assets_b": [...],
      "raw_a": 0, "raw_b": 0,
      "adj_a": 0.0, "adj_b": 0.0,
      "verdict": "favors X by N (P%)",
      "flags": [...],
      "parse_flags": [...]
    }
  }
}
```
Keyed by decision ID so `generate_today_page.py` can look up by ID in O(1).

### Decision: Today page renders analysis as a collapsed detail block
The inline analysis sits inside a `<details>` element with the verdict as the `<summary>`. This keeps the decision list scannable on mobile (one line per entry) while making the full breakdown available on tap/click — no JS required, `<details>` is native HTML.

## Risks / Trade-offs

[Risk: Description parsing breaks on unusual asset names] → Names with semicolons or " sends " in them would misparse. In practice KTC player/pick names never contain these strings. Flagged in `parse_flags` if the split produces unexpected results.

[Risk: `analyze_trade.py` import side effects] → The file currently has no module-level side effects beyond constant definitions. Safe to import. The `if __name__ == "__main__"` guard already exists.

[Risk: publish.yml race condition (existing)] → Both `sync.yml` and `publish.yml` push to the same branch. Adding `batch_analyze_trades.py` to `publish.yml` is a read-only cache step — it doesn't increase race risk.

## Migration Plan

1. Extract `analyze_trade_assets()` in `analyze_trade.py`; verify CLI still works
2. Create and smoke-test `batch_analyze_trades.py` against existing `decisions.json`
3. Update `generate_today_page.py`; verify Today page renders correctly with and without `trade_analysis.json`
4. Wire into `publish.yml`
