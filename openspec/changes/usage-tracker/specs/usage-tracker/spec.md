## Purpose

Surfaces weekly in-season rookie usage trends — snap share, target share, and red zone touches — with trajectory labels and free-agent flagging, so owners can identify breakout candidates on the waiver wire before they become unattainable.

## ADDED Requirements

### Requirement: Season-gated data fetch

`sync_usage.py` SHALL refuse to fetch or cache nflverse data when the NFL season type is not `"regular"`. It SHALL read season state from `cache/sleeper.json` (`nfl_state.season_type`); if the field is absent or the value is not `"regular"`, the script SHALL log the current season type, write a placeholder `cache/usage.json` with a `season_type` field and an empty `players` array, and exit 0 without error.

#### Scenario: Off-season or preseason run

- **WHEN** `nfl_state.season_type` is `"pre"`, `"post"`, or absent
- **THEN** `sync_usage.py` logs `"season_type=<value> — skipping usage fetch"`, writes a placeholder `cache/usage.json`, and exits 0

#### Scenario: Regular season run

- **WHEN** `nfl_state.season_type == "regular"`
- **THEN** `sync_usage.py` fetches nflverse weekly participation data for the current season and writes `cache/usage.json`

### Requirement: Rookie-only scope

The sync script SHALL fetch participation data only for players whose `years_exp` value in `cache/sleeper.json` `player_metadata` is `0` or `1` (first or second NFL year). Players not present in `player_metadata` SHALL be excluded. Non-skill positions (OL, K, P, LS, DB on defense) SHALL be excluded.

#### Scenario: Veteran filtered out

- **WHEN** a player in the nflverse data has `years_exp >= 2` in Sleeper player metadata
- **THEN** that player is excluded from `cache/usage.json`

#### Scenario: Rookie included

- **WHEN** a player has `years_exp` of `0` or `1` and is a skill-position player (QB, RB, WR, TE)
- **THEN** their weekly usage data is included in `cache/usage.json`

### Requirement: Weekly usage data fields

For each tracked rookie, `cache/usage.json` SHALL store an array of weekly records, each containing: `week` (integer), `snap_pct` (float 0–100 or null), `target_share` (float 0–100 or null), `route_participation` (float 0–100 or null), and `rz_touches` (integer or null). Null is used when a field is absent from the source data, not when the player played but recorded zero.

#### Scenario: Field absent from source

- **WHEN** nflverse does not provide a field for a given player-week
- **THEN** that field is stored as `null` in the cache, not `0`

#### Scenario: Player played but had zero targets

- **WHEN** a player played and the source records `0` targets
- **THEN** `target_share` is stored as `0`, not `null`

### Requirement: Trajectory classification

`generate_usage_page.py` SHALL classify each rookie's snap percentage trajectory using the last 3 available weeks of data (minimum 2 weeks required). Classification rules:

- **rising**: average of last 2 weeks > average of prior weeks by more than 5 percentage points
- **falling**: average of last 2 weeks < average of prior weeks by more than 5 percentage points
- **flat**: difference within 5 percentage points in either direction
- **insufficient data**: fewer than 2 non-null snap_pct values

The same classification logic SHALL apply to target share trajectory independently.

#### Scenario: Rising snap trajectory

- **WHEN** a rookie's snap % was 30% in week 3, 45% in week 4, and 50% in week 5
- **THEN** snap trajectory is classified as `"rising"`

#### Scenario: Insufficient data

- **WHEN** a rookie has only 1 week of non-null snap_pct data
- **THEN** snap trajectory is classified as `"insufficient data"` and rendered as such in `site/usage.md`

#### Scenario: Flat trajectory

- **WHEN** a rookie's snap % values across available weeks differ by 5 percentage points or less
- **THEN** snap trajectory is classified as `"flat"`

### Requirement: Roster vs. free-agent classification

`generate_usage_page.py` SHALL cross-reference each rookie against `cache/sleeper.json` rosters to determine whether the rookie is on any team's roster or is a free agent. It SHALL use normalized name matching (lowercase, strip punctuation, collapse spaces) against player names in the roster's `player_metadata`.

Free-agent rookies with a `"rising"` snap or target trajectory SHALL be visually flagged in `site/usage.md` as the primary call-to-action for the feature.

#### Scenario: Free-agent rookie with rising usage

- **WHEN** a rookie is not on any roster AND has a `"rising"` snap or target trajectory
- **THEN** that rookie appears in a dedicated "Rising Free Agents" section at the top of `site/usage.md` with a flag marker

#### Scenario: Rostered rookie

- **WHEN** a rookie is on any roster in the league
- **THEN** they appear in a separate "Rostered Rookies" section, not in the free-agent call-to-action section

### Requirement: College cross-reference

`generate_usage_page.py` SHALL attempt to match each rookie by normalized name against `cache/prospects.json` (stat-ranked prospects) and `cache/consensus.json` (manual consensus board). When a match is found, the rendered entry SHALL note the college stat rank and/or consensus rank inline. If neither cache exists, the cross-reference is silently skipped.

#### Scenario: Prospect cache match found

- **WHEN** a rookie's normalized name matches an entry in `cache/prospects.json`
- **THEN** their stat rank is shown inline in `site/usage.md`

#### Scenario: Prospect cache absent

- **WHEN** `cache/prospects.json` does not exist
- **THEN** `generate_usage_page.py` proceeds without error and omits the college cross-reference column

### Requirement: Injury-correlation flag

`generate_usage_page.py` SHALL read `cache/news.json` and check whether any headline in the same week as a rookie's rising usage contains a keyword matching an injury report for a player at the same position and team. The check is heuristic: look for the word "injured", "out", "IR", or "questionable" in a headline that also contains a player name from the same team/position group. When a correlation is detected, add an explicit note in the rendered output.

#### Scenario: Rising usage with same-week injury headline

- **WHEN** a rookie's snap share rose in week N AND a same-week news headline mentions an injury to a player on the same NFL team at the same position
- **THEN** `site/usage.md` notes: "Possible opportunity: [injured player] (injury reported same week)"

#### Scenario: No news data available

- **WHEN** `cache/news.json` is missing or empty
- **THEN** injury correlation is skipped silently; no error is raised

### Requirement: Preseason data label

When `sync_usage.py` runs during `season_type == "pre"` or detects that the available data weeks are preseason weeks (week number 0 or negative, or explicitly flagged in nflverse data), the placeholder `cache/usage.json` SHALL include `"data_note": "preseason — not representative"`. `generate_usage_page.py` SHALL render this note prominently at the top of `site/usage.md` so owners are not misled by preseason snap distributions.

#### Scenario: Preseason cache read by generator

- **WHEN** `cache/usage.json` contains `"data_note": "preseason — not representative"`
- **THEN** `site/usage.md` opens with a bold warning: "Data note: preseason data — trends are not representative of regular season roles"

### Requirement: Stale cache warning

If `cache/usage.json` was last updated more than 9 days ago (as determined by the `last_updated` field), `generate_usage_page.py` SHALL add a stale-data warning at the top of `site/usage.md`.

#### Scenario: Stale cache detected

- **WHEN** `cache/usage.json` `last_updated` is more than 9 days before the current UTC date
- **THEN** `site/usage.md` opens with: "Warning: usage data is stale (last updated: [date])"
