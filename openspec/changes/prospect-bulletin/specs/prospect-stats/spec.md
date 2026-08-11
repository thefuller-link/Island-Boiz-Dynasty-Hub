## Purpose

Fetches current-season college football production stats from the CFBD API and computes a dynasty-relevant composite score for each tracked skill-position player, writing the result to a local cache file.

## ADDED Requirements

### Requirement: Fetch college player stats from CFBD

The system SHALL fetch current-season stats for skill positions (QB, RB, WR, TE) from the CFBD API using the free-tier key stored in a GitHub Actions secret. The fetch SHALL cover passing, rushing, and receiving stats in a single season.

#### Scenario: Successful fetch

- **WHEN** the CFBD API is reachable and the season year is valid
- **THEN** the system writes raw stat entries for all available skill-position players to `cache/prospects.json`

#### Scenario: API unavailable

- **WHEN** the CFBD API returns a non-200 response or a network timeout
- **THEN** the system prints a descriptive error to stderr, leaves any existing `cache/prospects.json` untouched, and exits non-zero

### Requirement: Compute dynasty composite score

The system SHALL compute a dynasty-relevant composite score for each player using a documented, deterministic formula. The formula SHALL incorporate:
- **Volume**: receiving yards (WR/TE/RB) or passing yards (QB) normalized per game
- **Efficiency**: yards per target or yards per carry (position-appropriate)
- **Age penalty**: players older than the position's typical draft age SHALL have their score multiplied by a documented age-penalty factor (e.g., 0.85 per year over threshold)

The formula weights and thresholds SHALL be stored as named constants at the top of the script, not buried in expressions.

#### Scenario: Score computation produces a ranked list

- **WHEN** raw stats are available for at least one player
- **THEN** each player entry in `cache/prospects.json` includes a `composite_score` (float), a `stat_rank` (integer, 1 = highest), and the individual component values used in scoring

#### Scenario: Player missing a required stat component

- **WHEN** a stat field used in the formula is absent or null for a player
- **THEN** that component SHALL be treated as zero and the player is still scored; no exception is raised

### Requirement: Write prospects cache atomically

The system SHALL write `cache/prospects.json` using `tempfile.mkstemp` + `os.replace()` to prevent partial writes. The file SHALL include a `last_updated` ISO 8601 UTC timestamp and a `season` field recording which CFBD season year was fetched.

#### Scenario: Atomic write on success

- **WHEN** scoring completes without error
- **THEN** `cache/prospects.json` is replaced atomically with the new payload; the previous file is not left in a partial state

#### Scenario: Write failure

- **WHEN** the file write fails (e.g., disk full)
- **THEN** the temporary file is cleaned up and the original cache is left intact
