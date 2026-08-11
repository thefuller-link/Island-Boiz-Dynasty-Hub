## Purpose

Applies trade-evaluator logic to every trade entry in the decision log without requiring interactive input, producing a cache file the site can read at render time.

## ADDED Requirements

### Requirement: Batch analysis from decision log
The system SHALL read all entries with `type=trade` from `data/decisions.json` and produce a KTC value analysis for each, writing results to `cache/trade_analysis.json` keyed by decision entry `id`. The script SHALL run non-interactively (no TTY, no `input()` calls) and SHALL be invocable by GitHub Actions.

#### Scenario: Trade entries analyzed in batch
- **WHEN** `batch_analyze_trades.py` is run and `data/decisions.json` contains one or more `type=trade` entries
- **THEN** `cache/trade_analysis.json` contains one result object per trade ID with raw values, adjusted values, verdict string, and any flags

#### Scenario: No trade entries
- **WHEN** `data/decisions.json` has no `type=trade` entries
- **THEN** `cache/trade_analysis.json` is written with an empty results dict and a `last_updated` timestamp; the script exits successfully

### Requirement: Asset name resolution from description
The batch runner SHALL parse the trade description field (format: `"{owner_a} sends {assets}; {owner_b} sends {assets}"`) to extract asset names and SHALL resolve each name against `cache/ktc.json` using exact `name_key` match first, then single-word fuzzy matching. Unresolvable asset names SHALL be recorded as a `parse_flags` entry on the result rather than causing an error or omitting the entry.

#### Scenario: All assets resolve cleanly
- **WHEN** every asset name in a trade description matches a KTC player or pick exactly
- **THEN** the result for that trade ID includes fully populated `assets_a`, `assets_b`, `raw_a`, `raw_b`, `adj_a`, `adj_b`, and `verdict` fields with no `parse_flags`

#### Scenario: Unresolvable asset
- **WHEN** an asset name cannot be matched in KTC (e.g., a new player not yet in the KTC cache)
- **THEN** the result for that trade ID includes a `parse_flags` list naming the unresolved asset; computed values use only the resolved assets; the entry is still written to the cache

### Requirement: Stale-fallback cache write
If `data/decisions.json` or `cache/ktc.json` is missing, the script SHALL write a placeholder `cache/trade_analysis.json` with `results: {}`, a `data_note` explaining the missing input, and `last_updated` timestamp. It SHALL NOT exit non-zero solely due to missing inputs; it SHALL exit non-zero only on unexpected I/O errors.

#### Scenario: KTC cache missing
- **WHEN** `cache/ktc.json` does not exist when `batch_analyze_trades.py` is run
- **THEN** `cache/trade_analysis.json` is written with `results: {}` and a `data_note`; the script exits with code 0

### Requirement: Atomic cache write
`cache/trade_analysis.json` SHALL be written atomically via tempfile + `os.replace`, matching the pattern used by all other cache-writing scripts.

#### Scenario: Atomic write on success
- **WHEN** analysis completes without error
- **THEN** `cache/trade_analysis.json` is replaced in a single atomic rename; a partial file is never observable
