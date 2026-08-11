## MODIFIED Requirements

### Requirement: Trade value analysis on Today page
For each decision-log entry with `type=trade`, the Today page SHALL render the KTC value analysis from `cache/trade_analysis.json` directly beneath the vote-status row. The analysis display SHALL include: raw values for each side, adjusted values for each side, the verdict string (e.g., "favors MooSo by 420 (8.3%)"), and any flags (unresolved assets, positional redundancy, missing team_mode). If no analysis entry exists in the cache for a given trade ID, the vote row SHALL render as it does for non-trade entries — no error, no blank space, no placeholder.

#### Scenario: Analysis present for a trade entry
- **WHEN** `cache/trade_analysis.json` contains a result keyed to a trade's decision ID
- **THEN** the Today page renders the vote row followed immediately by an inline analysis block showing raw values, adjusted values, verdict, and flags (if any)

#### Scenario: Analysis absent for a trade entry
- **WHEN** `cache/trade_analysis.json` exists but has no entry for a specific trade ID
- **THEN** that trade's decision row renders normally (type, description, vote status) with no analysis block and no error

#### Scenario: trade_analysis.json missing entirely
- **WHEN** `cache/trade_analysis.json` does not exist
- **THEN** all decision entries render as before (vote status only); the page does not error and does not show a whole-page warning for this missing cache
