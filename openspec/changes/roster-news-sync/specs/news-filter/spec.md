## Purpose

Fetches the RotoWire NFL RSS feed and filters items against an expanded player set — rostered players plus a second tier of non-rostered players (trending adds, current-draft-class rookies, and a manual watchlist) — tagging each retained item with the category or categories that matched, and writing the results as structured JSON to the local cache.

## ADDED Requirements

### Requirement: Fetch RotoWire NFL RSS feed
The script SHALL request the RotoWire NFL RSS feed URL and parse all available items from the response.

#### Scenario: Successful RSS fetch
- **GIVEN** the RotoWire RSS endpoint is reachable
- **WHEN** the news sync script runs
- **THEN** all items in the feed are parsed before filtering is applied

### Requirement: Build expanded player filter set from four tiers
The script SHALL construct a unified player set from the following four tiers before evaluating any RSS item:

- **rostered**: all players currently on any co-owner's roster (from `cache/sleeper.json` → `rosters`)
- **trending**: players on Sleeper's trending-adds list (from `cache/sleeper.json` → `trending_adds`)
- **rookie**: all players with `years_exp == 0` in Sleeper's player metadata (from `cache/sleeper.json` → `player_metadata`), representing the current draft class regardless of roster status
- **watchlist**: players explicitly listed under `watchlist` in `config.yaml`; if `config.yaml` has no `watchlist` key or the file does not exist, this tier is treated as empty and the script continues normally

A player may belong to multiple tiers simultaneously. An RSS item is retained if its title or description mentions at least one player from any tier.

#### Scenario: Rostered player news is retained
- **GIVEN** "Justin Jefferson" is on a co-owner's roster
- **WHEN** the RSS feed contains an item mentioning "Justin Jefferson"
- **THEN** that item is included in `cache/news.json`

#### Scenario: Trending (non-rostered) player news is retained
- **GIVEN** "Malik Nabers" is on Sleeper's trending-adds list and is not on any co-owner's roster
- **WHEN** the RSS feed contains an item mentioning "Malik Nabers"
- **THEN** that item is included in `cache/news.json`

#### Scenario: Rookie (non-rostered, non-trending) player news is retained
- **GIVEN** "Emeka Egbuka" has `years_exp == 0` and is not rostered or trending
- **WHEN** the RSS feed contains an item mentioning "Emeka Egbuka"
- **THEN** that item is included in `cache/news.json`

#### Scenario: Watchlist player news is retained
- **GIVEN** "Tee Higgins" is listed under `watchlist` in `config.yaml` and is not rostered, trending, or a rookie
- **WHEN** the RSS feed contains an item mentioning "Tee Higgins"
- **THEN** that item is included in `cache/news.json`

#### Scenario: Untracked player news is excluded
- **GIVEN** a player appears in none of the four tiers
- **WHEN** the RSS feed contains an item mentioning only that player
- **THEN** that item is excluded from `cache/news.json`

#### Scenario: Missing watchlist is treated as empty
- **GIVEN** `config.yaml` exists but has no `watchlist` key
- **WHEN** the news sync script runs
- **THEN** the script proceeds normally, treating the watchlist tier as empty, without error

### Requirement: Tag each retained item with matched categories
Each retained RSS item SHALL include a `categories` field: a non-empty list of category strings drawn from `["rostered", "trending", "rookie", "watchlist"]` indicating which tiers contained a matching player. If a player belongs to multiple tiers, all matching categories SHALL be present.

#### Scenario: Item matched on single tier
- **GIVEN** an RSS item mentions a player who is rostered but not in any other tier
- **WHEN** `cache/news.json` is read
- **THEN** that item's `categories` field is `["rostered"]`

#### Scenario: Item matched on multiple tiers
- **GIVEN** an RSS item mentions a player who is both rostered and on the trending-adds list
- **WHEN** `cache/news.json` is read
- **THEN** that item's `categories` field contains both `"rostered"` and `"trending"`

### Requirement: Structured JSON output
Each retained RSS item SHALL be written as a JSON object with at minimum the fields: `title`, `description`, `published`, `link`, and `categories`.

#### Scenario: Output structure is consistent
- **GIVEN** a news item is retained after filtering
- **WHEN** `cache/news.json` is read
- **THEN** each item object contains `title`, `description`, `published`, `link`, and `categories` fields

### Requirement: Write last_updated timestamp
The output JSON SHALL include a top-level `last_updated` field containing an ISO 8601 UTC timestamp of when the successful fetch and filter completed.

#### Scenario: Timestamp present after successful run
- **GIVEN** the RSS fetch and filter succeeds
- **WHEN** the script completes
- **THEN** `cache/news.json` has a `last_updated` field parseable as ISO 8601

### Requirement: Require sleeper cache before filtering
The script SHALL read all Sleeper-derived tier data (`rosters`, `trending_adds`, `player_metadata`) from `cache/sleeper.json`. If that file does not exist or cannot be parsed, the script SHALL exit with a non-zero status and a descriptive error, without writing or overwriting `cache/news.json`.

#### Scenario: Sleeper cache missing
- **GIVEN** `cache/sleeper.json` does not exist
- **WHEN** the news sync script runs
- **THEN** it exits with a non-zero exit code and writes no news cache file

#### Scenario: Sleeper cache missing required keys
- **GIVEN** `cache/sleeper.json` exists but lacks the `trending_adds` or `player_metadata` keys
- **WHEN** the news sync script runs
- **THEN** it exits with a non-zero exit code and a descriptive error identifying the missing key

### Requirement: Graceful stale fallback
If the RotoWire RSS fetch fails or times out, the script SHALL retain the existing `cache/news.json` without modification and exit with a non-zero status code.

#### Scenario: RSS timeout — news cache preserved
- **GIVEN** `cache/news.json` exists from a prior successful run
- **WHEN** the RotoWire RSS endpoint times out
- **THEN** `cache/news.json` is unchanged and the script exits with a non-zero exit code
