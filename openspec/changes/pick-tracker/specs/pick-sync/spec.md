## Purpose

Derives which future draft picks each team currently owns by replaying Sleeper transaction history, merges current KTC market values onto each pick, applies manual overrides for picks Sleeper can't resolve cleanly, and writes the result to `cache/picks.json` so downstream scripts have a single authoritative pick ledger.

## ADDED Requirements

### Requirement: Derive pick ownership from Sleeper transactions
The script SHALL read transaction history from `cache/sleeper.json` and replay pick-trade entries to compute the current owner of each future pick for the years covered (current season through current season + 2).

#### Scenario: Pick never traded
- **WHEN** no transaction in the history moves a pick
- **THEN** the pick's current owner equals the team that originally held it (the team whose roster_id the pick belongs to by default in Sleeper)

#### Scenario: Pick traded once
- **WHEN** one transaction transfers a pick from Team A to Team B
- **THEN** the pick's current owner is Team B with provenance "originally Team A's"

#### Scenario: Pick traded multiple times
- **WHEN** multiple transactions transfer the same pick across different owners
- **THEN** the final owner after the last transaction is recorded; provenance still traces back to the original owning team

### Requirement: Attach KTC value to each pick
The script SHALL look up each pick's label in `cache/ktc.json` picks list and record the matched value alongside the pick entry.

#### Scenario: Exact label match found
- **WHEN** a pick's label (e.g., "2027 Mid 1st") matches an entry in `cache/ktc.json` picks
- **THEN** the `value` field on the pick entry is set to the matched KTC value

#### Scenario: No KTC match for pick
- **WHEN** a pick's label does not match any entry in `cache/ktc.json`
- **THEN** the pick entry is written with `value: null` and `value_source: "unmatched"` so callers can distinguish zero-value from unknown-value

### Requirement: Apply manual overrides
The script SHALL read `data/pick_overrides.json` and, for each override entry, replace or supplement the Sleeper-derived ownership record for the matching pick.

#### Scenario: Override corrects an uncertain pick
- **WHEN** `data/pick_overrides.json` contains an entry for a pick that Sleeper marked as uncertain
- **THEN** the override's `owner`, `provenance`, and `note` fields replace the uncertain entry in the output

#### Scenario: Override adds a pick not in Sleeper data
- **WHEN** `data/pick_overrides.json` contains a pick with no corresponding Sleeper record
- **THEN** the pick is added to `cache/picks.json` with `source: "manual"` and the override's fields

#### Scenario: Override file missing
- **WHEN** `data/pick_overrides.json` does not exist
- **THEN** the script proceeds without overrides; no error is raised

### Requirement: Flag uncertain picks
The script SHALL mark picks as uncertain when their ownership cannot be confidently determined from Sleeper data (e.g., conditional trades, pending transactions, incomplete transaction records).

#### Scenario: Pick involved in a conditional trade
- **WHEN** a pick appears in a transaction record tagged as conditional or otherwise unresolved in Sleeper's data
- **THEN** the pick's `uncertain: true` field is set and a human-readable `note` explains why

#### Scenario: Pick ownership is unambiguous
- **WHEN** pick ownership is fully determinable from Sleeper transaction history
- **THEN** the pick entry has `uncertain: false` and no note is added

### Requirement: Validate required cache files at startup
The script SHALL verify that `cache/sleeper.json` and `cache/ktc.json` exist before proceeding and exit non-zero with a descriptive error naming which file is missing if either is absent.

#### Scenario: One or both cache files missing
- **WHEN** `cache/sleeper.json` or `cache/ktc.json` does not exist
- **THEN** the script prints which file is missing and which sync script to run, then exits non-zero without writing `cache/picks.json`

### Requirement: Atomic output write
The script SHALL write `cache/picks.json` atomically so a partial run never corrupts the existing file.

#### Scenario: Write completes without interruption
- **WHEN** all data processing completes successfully
- **THEN** `cache/picks.json` is either the previous complete file or the new complete file — never a partial write

### Requirement: Output structure
`cache/picks.json` SHALL contain a `picks` array (each entry: `year`, `round`, `label`, `original_owner`, `current_owner`, `provenance`, `value`, `value_source`, `uncertain`, `note`, `source`) and a `last_updated` ISO 8601 UTC timestamp.

#### Scenario: Successful run with mixed picks
- **WHEN** the script completes with a mix of traded, untraded, and uncertain picks
- **THEN** `cache/picks.json` contains all derived picks in the `picks` array with correct field values, and `last_updated` reflects the time of the write
