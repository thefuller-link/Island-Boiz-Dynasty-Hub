## Purpose

Stores and serves a public consensus big board as a rankable list of dynasty-relevant college prospects, used as a second signal alongside stat-based ranks in the bulletin.

## ADDED Requirements

### Requirement: Maintain a consensus big board in cache

The system SHALL maintain `cache/consensus.json` containing a ranked list of college prospects drawn from a public consensus source. The initial implementation MAY use a manually-updated JSON file in `data/consensus_board.json` as the source when no reliably scriptable free endpoint exists; `sync_consensus.py` SHALL copy it to cache with a timestamp.

#### Scenario: Consensus source is a manually-updated file

- **WHEN** `data/consensus_board.json` exists and is valid JSON
- **THEN** `sync_consensus.py` writes its contents (plus `last_updated`) to `cache/consensus.json` and exits 0

#### Scenario: Consensus source file is missing

- **WHEN** `data/consensus_board.json` does not exist
- **THEN** the system prints a descriptive message to stderr ("No consensus board found — create data/consensus_board.json or configure a live source") and exits non-zero

### Requirement: Consensus board schema

Each entry in `cache/consensus.json` SHALL include: `name` (string), `position` (string), `school` (string), `consensus_rank` (integer), and optionally `source` (string, e.g., "manual", "dynastyprocess"). The list SHALL be sorted by `consensus_rank` ascending.

#### Scenario: Valid board loaded

- **WHEN** `cache/consensus.json` is read by `generate_bulletin.py`
- **THEN** each entry has at minimum `name` and `consensus_rank` fields; missing optional fields do not cause an error

#### Scenario: Board contains duplicate ranks

- **WHEN** two entries share the same `consensus_rank`
- **THEN** the system resolves the tie by secondary sort on `name` alphabetically; no error is raised

### Requirement: Stale fallback for consensus data

The system SHALL NOT overwrite an existing `cache/consensus.json` with an empty or error result. If the source is unavailable or produces zero entries, the existing cache SHALL be left untouched and the system exits non-zero.

#### Scenario: Source produces zero entries

- **WHEN** the consensus source file exists but parses to an empty list
- **THEN** `cache/consensus.json` is not overwritten; the system prints a warning and exits non-zero
