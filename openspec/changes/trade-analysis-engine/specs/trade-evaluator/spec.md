## Purpose

Evaluates a proposed dynasty trade by summing KTC values per side, applying team-mode pick-weight adjustments, flagging positional redundancy from current roster data, and producing a structured verdict so owners have a neutral quantitative baseline for trade discussions.

## ADDED Requirements

### Requirement: Accept trade input via CLI prompts
The script SHALL accept a proposed trade through interactive prompts: which owner is on each side, and which players/picks each side sends.

#### Scenario: Valid trade input provided
- **WHEN** the user provides two sides with at least one asset each
- **THEN** the script proceeds to value lookup and analysis

#### Scenario: Asset entered for unknown player
- **WHEN** the user enters a player name that cannot be matched in `cache/ktc.json`
- **THEN** the script notifies the user, prompts to re-enter or skip, and does not silently assign a value of zero

#### Scenario: Pick entered as asset
- **WHEN** the user enters a pick (e.g., "2026 1st") rather than a player name
- **THEN** the script matches it against the `picks` list in `cache/ktc.json` and uses the corresponding value

### Requirement: Compute raw value differential
The script SHALL sum each side's asset values and output the raw difference and the percentage skew.

#### Scenario: One side has higher total value
- **WHEN** Side A's total value exceeds Side B's
- **THEN** the verdict states Side A's total, Side B's total, the absolute differential, and the percentage advantage for Side A

#### Scenario: Values are equal
- **WHEN** both sides' totals are within 1% of each other
- **THEN** the verdict states the trade is approximately even

### Requirement: Apply team-mode pick-weight adjustments
The script SHALL read each owner's `team_mode` from `config.yaml` (`contending`, `retooling`, or `rebuilding`) and apply a multiplier to future draft picks received by or sent by that owner.

#### Scenario: Rebuilding owner receives a future pick
- **WHEN** a rebuilding team acquires a future draft pick in the trade
- **THEN** the pick's effective value in that team's favor is multiplied by a rebuild weight (>1.0)

#### Scenario: Contending owner sends a future pick
- **WHEN** a contending team gives up a future draft pick
- **THEN** the pick's effective value in that team's cost is multiplied by a contend weight (<1.0), reflecting that the pick is less costly relative to near-term win-now value

#### Scenario: team_mode missing from config
- **WHEN** `config.yaml` does not include `team_mode` for an owner involved in the trade
- **THEN** the script applies neutral weighting (multiplier = 1.0) and flags the missing mode in the verdict output

### Requirement: Flag positional redundancy
The script SHALL cross-reference the receiving team's current rostered players from `cache/sleeper.json` and flag when the team would hold three or more starters of the same position after acquiring the traded asset.

#### Scenario: Acquiring team already has two starters at position
- **WHEN** a team acquires a player at a position where they already roster two starter-tier players at that same position
- **THEN** the verdict includes a consideration flag: "[Owner] already has [N] rostered [POS]"

#### Scenario: No redundancy detected
- **WHEN** the acquiring team has fewer than two existing starters at the acquired player's position
- **THEN** no positional redundancy flag is added to the verdict

### Requirement: Output structured verdict
The script SHALL print a structured verdict that includes value totals per side, the differential, which team it favors (or even), and up to two flagged considerations.

#### Scenario: Complete verdict printed
- **WHEN** analysis completes without errors
- **THEN** the output includes: Side A total, Side B total, differential, favored side (or "approximately even"), and any applicable flags (team-mode note, positional redundancy)

#### Scenario: KTC cache is stale
- **WHEN** `cache/ktc.json` exists but `last_updated` is more than 48 hours old
- **THEN** the verdict includes a warning: "KTC values last updated [timestamp] — may not reflect current market"

### Requirement: Offer decision-log integration
After printing the verdict, the script SHALL ask whether to append a draft entry to `data/decisions.json` using the same format as `log_decision.py`.

#### Scenario: User opts in to decision-log entry
- **WHEN** the user answers yes to the decision-log prompt
- **THEN** the script creates a new entry in `data/decisions.json` of type "trade" with the trade description pre-filled from the analyzed trade, the proposer set to the owner who initiated the analysis, all other owners set to pending, and the verdict appended to the rationale field

#### Scenario: User opts out of decision-log entry
- **WHEN** the user answers no to the decision-log prompt
- **THEN** no entry is written and the script exits cleanly

### Requirement: Validate required cache files at startup
The script SHALL check that `cache/ktc.json` and `cache/sleeper.json` both exist before proceeding and exit with a descriptive error if either is missing.

#### Scenario: One or both cache files missing
- **WHEN** `cache/ktc.json` or `cache/sleeper.json` does not exist
- **THEN** the script prints which file is missing and instructs the user to run the appropriate sync script, then exits non-zero
