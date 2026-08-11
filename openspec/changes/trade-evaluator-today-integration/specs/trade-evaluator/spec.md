## MODIFIED Requirements

### Requirement: Importable computation function
The `analyze_trade.py` module SHALL expose an `analyze_trade_assets(owner_a, assets_a, owner_b, assets_b, ktc, sleeper, team_mode)` function that runs the full value computation (raw totals, adjusted totals, redundancy flags, verdict string) and returns a structured result dict without printing to stdout or reading from stdin. The existing interactive `main()` SHALL be updated to call this function rather than duplicating the computation inline; CLI behavior and output format SHALL be unchanged.

#### Scenario: Programmatic call without TTY
- **WHEN** `analyze_trade_assets()` is called with fully populated asset lists and loaded cache dicts
- **THEN** it returns a dict containing `raw_a`, `raw_b`, `adj_a`, `adj_b`, `verdict`, and `flags` without requiring any stdin input or producing any stdout output

#### Scenario: Interactive CLI unchanged
- **WHEN** `python scripts/analyze_trade.py` is run interactively with valid stdin input
- **THEN** behavior, prompts, and printed output are identical to before this change
