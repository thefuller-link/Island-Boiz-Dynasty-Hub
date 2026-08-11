## Purpose

Fetches our dynasty league's current rosters, active matchups, transactions, trending-adds, and player metadata from Sleeper's public REST API and writes them as structured JSON to the local cache for use by downstream features.

## ADDED Requirements

### Requirement: Fetch league rosters
The script SHALL request all roster data for the configured league ID from the Sleeper API and produce a JSON output keyed by owner user ID, including each owner's player list.

#### Scenario: Successful roster fetch
- **GIVEN** the Sleeper API is reachable and the league ID is configured
- **WHEN** the sync script runs
- **THEN** `cache/sleeper.json` is written with a top-level `rosters` key mapping each owner's user ID to their list of Sleeper player IDs

### Requirement: Fetch active matchups
The script SHALL request the current NFL week's matchup data for the league and include it in the output.

#### Scenario: Matchups written to cache
- **GIVEN** the Sleeper API returns matchup data for the current week
- **WHEN** the sync script runs
- **THEN** `cache/sleeper.json` contains a `matchups` key with the current week's matchup objects

### Requirement: Fetch recent transactions
The script SHALL request recent waiver and trade transactions for the league and include them in the output.

#### Scenario: Transactions written to cache
- **GIVEN** the Sleeper API returns transaction records
- **WHEN** the sync script runs
- **THEN** `cache/sleeper.json` contains a `transactions` key listing the most recent transactions

### Requirement: Write last_updated timestamp
The output JSON SHALL include a top-level `last_updated` field containing an ISO 8601 UTC timestamp of the successful fetch.

#### Scenario: Timestamp present after successful run
- **GIVEN** the Sleeper API responds successfully
- **WHEN** the sync script completes
- **THEN** `cache/sleeper.json` has a `last_updated` field parseable as ISO 8601

### Requirement: Graceful stale fallback
If any Sleeper API call fails or times out, the script SHALL retain the existing `cache/sleeper.json` without modification and exit with a non-zero status code.

#### Scenario: API timeout — cache preserved
- **GIVEN** `cache/sleeper.json` exists from a prior successful run
- **WHEN** the Sleeper API times out during the sync
- **THEN** `cache/sleeper.json` is unchanged and the script exits with a non-zero exit code

#### Scenario: No cache exists and API fails
- **GIVEN** `cache/sleeper.json` does not exist
- **WHEN** the Sleeper API is unreachable
- **THEN** the script exits with a non-zero exit code and writes no cache file

### Requirement: Fetch trending-adds player list
The script SHALL request Sleeper's league-wide trending-adds list (most-added players over the past 24 hours) and write the result to `cache/sleeper.json` under a `trending_adds` key as an ordered list of player IDs.

#### Scenario: Trending-adds written to cache
- **GIVEN** the Sleeper trending-adds endpoint is reachable
- **WHEN** the sync script runs
- **THEN** `cache/sleeper.json` contains a `trending_adds` key with an ordered list of player IDs

#### Scenario: Trending-adds failure — full sync aborted
- **GIVEN** the trending-adds endpoint times out or returns an error
- **WHEN** the sync script runs
- **THEN** `cache/sleeper.json` is left unchanged and the script exits with a non-zero exit code

### Requirement: Fetch and cache player metadata
The script SHALL request Sleeper's full NFL player metadata endpoint and write a subset of each player's data — at minimum `player_id`, `full_name`, and `years_exp` — to `cache/sleeper.json` under a `player_metadata` key, keyed by `player_id`.

#### Scenario: Player metadata written to cache
- **GIVEN** the Sleeper player-metadata endpoint is reachable
- **WHEN** the sync script runs
- **THEN** `cache/sleeper.json` contains a `player_metadata` key whose values each include `full_name` and `years_exp`

#### Scenario: Player metadata failure — full sync aborted
- **GIVEN** the player-metadata endpoint is unreachable
- **WHEN** the sync script runs
- **THEN** `cache/sleeper.json` is left unchanged and the script exits with a non-zero exit code

### Requirement: No hardcoded credentials
The league ID and any future configuration SHALL be read from environment variables; no values SHALL be embedded in the script source.

#### Scenario: League ID from environment
- **GIVEN** the environment variable `SLEEPER_LEAGUE_ID` is set
- **WHEN** the sync script runs
- **THEN** it uses that value as the league ID for all API requests

#### Scenario: Missing league ID
- **GIVEN** `SLEEPER_LEAGUE_ID` is not set
- **WHEN** the sync script runs
- **THEN** the script exits with a non-zero exit code and a descriptive error message without making any API calls
