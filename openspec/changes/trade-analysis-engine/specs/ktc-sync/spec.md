## Purpose

Fetches current KeepTradeCut dynasty trade values for players and draft picks and caches them locally so other scripts can perform value lookups without hitting the remote endpoint at runtime.

## ADDED Requirements

### Requirement: Fetch KTC dynasty values
The script SHALL retrieve dynasty trade values for NFL players and draft picks from KeepTradeCut's public data endpoint and write the result to `cache/ktc.json`.

#### Scenario: Successful fetch
- **WHEN** the KTC endpoint returns valid data
- **THEN** `cache/ktc.json` is written with a `players` list (each entry: `player_name`, `position`, `team`, `value`), a `picks` list (each entry: `pick_label`, `value`), and a `last_updated` ISO 8601 UTC timestamp

#### Scenario: HTTP error on fetch
- **WHEN** the KTC endpoint returns a non-2xx response or a network error occurs
- **THEN** the script prints a descriptive error to stderr, does NOT overwrite `cache/ktc.json`, and exits with a non-zero code

#### Scenario: Stale cache exists when fetch fails
- **WHEN** the KTC endpoint is unreachable and `cache/ktc.json` already exists from a prior run
- **THEN** the existing file is preserved unchanged and the error message includes the stale cache's `last_updated` timestamp

### Requirement: Expose cache staleness timestamp
The `cache/ktc.json` file SHALL include a `last_updated` field so consumers can surface how current the values are.

#### Scenario: Timestamp written on successful update
- **WHEN** a successful fetch completes and `cache/ktc.json` is written
- **THEN** `last_updated` equals the UTC time of the write, formatted as ISO 8601

#### Scenario: Timestamp preserved on failure
- **WHEN** a fetch fails and the prior cache is retained
- **THEN** `last_updated` in `cache/ktc.json` still reflects the last successful write, not the failed attempt

### Requirement: Atomic write
The script SHALL write `cache/ktc.json` atomically so a partial fetch never leaves a corrupt file on disk.

#### Scenario: Write completes without interruption
- **WHEN** the fetch succeeds and the file is written
- **THEN** `cache/ktc.json` is either the previous complete file or the new complete file — never a partial write

### Requirement: Player name normalization
The script SHALL store player names in a normalized form (lowercase, stripped of punctuation) in an additional `name_key` field on each player entry to support fuzzy matching by the trade evaluator.

#### Scenario: Name key generated
- **WHEN** a player entry is written to `cache/ktc.json`
- **THEN** each entry includes both `player_name` (original) and `name_key` (lowercase, no punctuation, single spaces)
