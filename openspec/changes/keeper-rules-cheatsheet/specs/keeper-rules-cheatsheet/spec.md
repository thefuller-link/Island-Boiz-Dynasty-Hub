## Purpose

Provides an always-current league rules reference page by combining auto-synced Sleeper settings with a manually-maintained supplementary file, so owners can look up roster limits, scoring, and group agreements in one place without digging through the Sleeper app.

## ADDED Requirements

### Requirement: League settings sync

`sync_league_settings.py` SHALL fetch league settings from `GET /v1/league/{league_id}` using the `league_id` from `config.yaml`. On success it SHALL write the response to `cache/league_settings.json` atomically. On any HTTP or network error it SHALL print a descriptive error to stderr and exit non-zero; no stale fallback is used for this script since settings rarely change and the page generator handles a missing cache gracefully.

#### Scenario: Successful fetch

- **WHEN** the Sleeper API returns a valid league settings object
- **THEN** `cache/league_settings.json` is written with the full response plus a `last_updated` ISO 8601 UTC timestamp field appended at the top level

#### Scenario: Network error

- **WHEN** the Sleeper API call fails with an HTTP error or timeout
- **THEN** `sync_league_settings.py` prints the error to stderr and exits non-zero; `cache/league_settings.json` is not modified

### Requirement: League settings page — auto-synced section

`generate_rules_page.py` SHALL read `cache/league_settings.json` and render a "League Settings" section in `site/rules.md` containing at minimum: roster size limits, number of starters by position, scoring type (PPR/half-PPR/standard), trade deadline (if set), and waiver type. It SHALL include a `_Last synced: <timestamp>_` line at the end of this section.

If `cache/league_settings.json` is missing, the section SHALL render with a "settings not yet synced" placeholder rather than failing.

#### Scenario: Full cache available

- **WHEN** `cache/league_settings.json` exists and contains valid JSON
- **THEN** `site/rules.md` renders roster limits, starter slots, scoring type, and a last-synced timestamp in the auto-synced section

#### Scenario: Cache missing

- **WHEN** `cache/league_settings.json` does not exist
- **THEN** `site/rules.md` renders a placeholder message in the auto-synced section: "League settings not yet synced — run `python scripts/sync_league_settings.py`"

### Requirement: Keeper settings rendering

When the synced league settings include keeper-related fields (e.g., `max_keepers > 0` or a keeper deadline), the auto-synced section SHALL include a "Keeper Rules" subsection with those fields rendered plainly. When no keeper fields are configured (or `max_keepers == 0` or the field is absent), the subsection SHALL be omitted entirely — the page SHALL NOT render empty or "N/A" keeper fields.

#### Scenario: Keeper league

- **WHEN** `cache/league_settings.json` contains `max_keepers` greater than 0
- **THEN** `site/rules.md` includes a "Keeper Rules" subsection listing max keepers and any deadline or cost fields present in the settings

#### Scenario: Non-keeper league

- **WHEN** `cache/league_settings.json` does not contain `max_keepers` or `max_keepers == 0`
- **THEN** `site/rules.md` does not include a "Keeper Rules" subsection

### Requirement: League rules page — manual supplementary section

`generate_rules_page.py` SHALL read `data/league_rules_extra.json` and render a clearly labeled "Group Agreements" section in `site/rules.md` after the auto-synced section. This section SHALL display each rule entry as a plain list item. The section SHALL include a `_Last updated by: <author> on <date>_` attribution line using the `last_updated_by` and `last_updated` fields from the file.

If `data/league_rules_extra.json` is missing, the section SHALL render with a "no group agreements on file" placeholder.

#### Scenario: Manual rules present

- **WHEN** `data/league_rules_extra.json` exists and contains one or more rule entries
- **THEN** `site/rules.md` renders a "Group Agreements" section with each rule as a list item and the attribution line

#### Scenario: Manual rules file absent

- **WHEN** `data/league_rules_extra.json` does not exist
- **THEN** `site/rules.md` renders "No group agreements on file" in the manual section without error

### Requirement: Clear source labeling

`site/rules.md` SHALL clearly distinguish auto-synced content from manually-maintained content. The auto-synced section SHALL carry an explicit label (e.g., "_Auto-synced from Sleeper_") and the manual section SHALL carry an explicit label (e.g., "_Manually maintained — edit `data/league_rules_extra.json` to update_"). The two sections SHALL be separated by a visible Markdown divider.

#### Scenario: Both sources present

- **WHEN** both `cache/league_settings.json` and `data/league_rules_extra.json` exist
- **THEN** `site/rules.md` contains both sections with their respective labels and a divider between them, making the source of each piece of information unambiguous
