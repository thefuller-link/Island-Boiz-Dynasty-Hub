## Purpose

Merges stat-based prospect ranks with public consensus ranks to produce a weekly bulletin page listing the top dynasty-relevant college players with divergence flags, written to the static site.

## ADDED Requirements

### Requirement: Merge stat and consensus ranks

The system SHALL merge `cache/prospects.json` and `cache/consensus.json` by player name (case-insensitive, punctuation-normalized). Each merged entry SHALL carry both `stat_rank` and `consensus_rank`. Players present in only one source SHALL be included with the missing rank shown as "N/A".

#### Scenario: Player appears in both sources

- **WHEN** a player's normalized name matches in both caches
- **THEN** the merged entry has numeric values for both `stat_rank` and `consensus_rank`

#### Scenario: Player appears in only one source

- **WHEN** a player name is in prospects but not consensus (or vice versa)
- **THEN** the merged entry is included with the missing rank set to null and rendered as "N/A" in the bulletin

### Requirement: Select top 15-20 bulletin entries

The system SHALL include the top 15 entries by default and up to 20 when additional entries are tied at the 15th rank. Selection SHALL be based on the lower (better) of `stat_rank` and `consensus_rank` when both are present; entries with only one rank use that rank; entries with neither rank are excluded.

#### Scenario: Standard selection

- **WHEN** at least 15 merged entries exist
- **THEN** `site/bulletin.md` contains exactly 15 entries (or up to 20 on tie)

#### Scenario: Fewer than 15 total merged entries

- **WHEN** combined sources produce fewer than 15 names
- **THEN** all available entries are shown; no padding or error

### Requirement: Flag notable divergence

The system SHALL compute the rank difference (`consensus_rank - stat_rank`) for each entry where both ranks are numeric. When the absolute difference exceeds a documented threshold (default: 5 ranks), the system SHALL include a one-line divergence note. The note SHALL follow a template: "stat rank #{stat_rank}, consensus #{consensus_rank} -- {direction} {interpretation}" where direction is "efficiency spiking, market hasn't caught up" (stat better) or "market leader, stats haven't backed it up" (consensus better).

#### Scenario: Divergence above threshold

- **WHEN** |consensus_rank - stat_rank| > DIVERGENCE_THRESHOLD
- **THEN** the bulletin entry includes a non-empty divergence note

#### Scenario: Ranks close together

- **WHEN** |consensus_rank - stat_rank| <= DIVERGENCE_THRESHOLD
- **THEN** the divergence note field is empty and no flag line is shown

### Requirement: Bulletin output format

The system SHALL write `site/bulletin.md` as Markdown. Each entry SHALL appear as a list item or table row with: position, school, stat rank, consensus rank, and divergence note (if any). The page SHALL include an H1 title ("Prospect Bulletin"), a `_Last updated: {ISO timestamp}_` footer, and a note when either cache is stale (older than 8 days).

#### Scenario: Bulletin rendered successfully

- **WHEN** both caches exist and contain entries
- **THEN** `site/bulletin.md` is written with an H1, at least one entry, and a last-updated footer

#### Scenario: Stale cache detected

- **WHEN** `cache/prospects.json` or `cache/consensus.json` was last updated more than 8 days ago
- **THEN** the bulletin page includes a visible warning line noting which cache is stale

### Requirement: Graceful fallback when caches are missing

If `cache/prospects.json` is absent, the system SHALL write `site/bulletin.md` with a placeholder message ("Prospect data unavailable -- run python scripts/sync_prospects.py first") and exit 0. If `cache/consensus.json` is absent, the bulletin SHALL be generated using stat ranks only with a visible note that consensus data is missing.

#### Scenario: Prospects cache missing

- **WHEN** `cache/prospects.json` does not exist
- **THEN** `site/bulletin.md` is written with a placeholder and the script exits 0

#### Scenario: Consensus cache missing

- **WHEN** `cache/consensus.json` does not exist but `cache/prospects.json` does
- **THEN** `site/bulletin.md` is generated with stat-rank-only entries and a note that consensus data is absent
