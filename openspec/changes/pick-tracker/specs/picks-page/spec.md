## Purpose

Renders a human-readable Markdown page from `cache/picks.json` showing all future picks owned by each team (per-team view) and a consolidated full-league listing, with KTC values and provenance so owners can quickly assess their draft capital.

## ADDED Requirements

### Requirement: Per-team picks section
The page SHALL include one section per owner showing that owner's currently held future picks, sorted by year then round.

#### Scenario: Owner holds multiple picks across years
- **WHEN** an owner holds picks in multiple draft years
- **THEN** their section lists all picks sorted ascending by year, then by round within each year

#### Scenario: Owner holds no future picks
- **WHEN** an owner has traded away all tracked picks and holds none
- **THEN** their section still appears with a "No future picks" placeholder

### Requirement: Full-league picks table
The page SHALL include a full-league section listing every tracked future pick across all three owners in a single sorted table (year → round → owner), so the complete draft capital picture is visible in one view.

#### Scenario: Full-league table rendered
- **WHEN** `cache/picks.json` contains picks from multiple owners
- **THEN** the full-league section shows all picks ordered by year then round, with columns: year, round, current owner, value, and provenance

### Requirement: Show KTC value on each pick entry
Each pick entry in both the per-team and full-league views SHALL display its KTC value. Picks with no matched value SHALL be shown with "N/A" rather than a blank or zero.

#### Scenario: Pick has a matched value
- **WHEN** a pick's `value` field is a non-null integer
- **THEN** the value is displayed alongside the pick label

#### Scenario: Pick has no matched value
- **WHEN** a pick's `value` is null or `value_source` is "unmatched"
- **THEN** the value column shows "N/A"

### Requirement: Show provenance on traded picks
Any pick whose `current_owner` differs from `original_owner` SHALL display provenance text indicating the original owning team (e.g., "via LWFuller").

#### Scenario: Pick was traded
- **WHEN** `current_owner != original_owner`
- **THEN** the pick row or entry includes provenance text

#### Scenario: Pick was never traded
- **WHEN** `current_owner == original_owner`
- **THEN** no provenance annotation is shown

### Requirement: Flag uncertain picks visibly
Picks marked `uncertain: true` in `cache/picks.json` SHALL be visually distinguished in the output with a flag and their associated note.

#### Scenario: Uncertain pick rendered
- **WHEN** a pick has `uncertain: true`
- **THEN** the pick is annotated with "[?]" or equivalent indicator and the `note` text is shown inline or nearby

#### Scenario: No uncertain picks
- **WHEN** all picks have `uncertain: false`
- **THEN** no uncertainty annotations appear in the output

### Requirement: Staleness timestamp
The page SHALL include the `last_updated` timestamp from `cache/picks.json` so readers know how current the data is.

#### Scenario: Timestamp rendered
- **WHEN** `site/picks.md` is generated
- **THEN** the page footer or header includes "Last updated: [timestamp]" derived from `cache/picks.json`

### Requirement: Handle empty or missing cache
If `cache/picks.json` is missing or its `picks` array is empty, the script SHALL write a placeholder page rather than crashing, and exit 0.

#### Scenario: Cache file missing
- **WHEN** `cache/picks.json` does not exist
- **THEN** `site/picks.md` is written with a "No pick data available — run sync first" placeholder and the script exits 0

#### Scenario: Picks array is empty
- **WHEN** `cache/picks.json` exists but `picks` is an empty array
- **THEN** `site/picks.md` is written with a "No future picks tracked" placeholder
