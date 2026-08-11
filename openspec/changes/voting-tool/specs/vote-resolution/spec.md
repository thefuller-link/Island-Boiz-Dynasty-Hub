## Purpose

Computes and records resolution status for each decision-log entry based on owner responses, applying majority or unanimous rules depending on the assets involved, and writes the outcome back into the decision data so the site and CLI can surface it without recomputing.

## ADDED Requirements

### Requirement: Default resolution rule is majority

For transaction entries (type: trade, waiver-claim, roster-move, other), the system SHALL resolve a decision as "approved" when at least 2 of 3 owners have responded "approve". The system SHALL resolve as "vetoed" when at least 2 of 3 owners have responded "veto". If fewer than 2 owners have responded (excluding abstain), the entry SHALL remain "pending".

#### Scenario: Two approvals out of three owners

- **WHEN** two owners respond "approve" and the third responds "pending" or "abstain"
- **THEN** resolution is "approved" with reason noting majority approval

#### Scenario: One approve, one veto, one pending

- **WHEN** no two owners share the same approve/veto response
- **THEN** resolution is "pending"

#### Scenario: Two vetoes

- **WHEN** two owners respond "veto"
- **THEN** resolution is "vetoed" with reason noting majority veto

### Requirement: Abstain-to-majority resolution

If exactly one owner responds "abstain" and the other two owners agree (both approve or both veto), the system SHALL resolve using the two non-abstaining owners' votes and record resolution as "approved" or "vetoed" with reason "abstain-to-majority".

#### Scenario: Two approve, one abstain

- **WHEN** two owners respond "approve" and one responds "abstain"
- **THEN** resolution is "approved", reason is "abstain-to-majority"

#### Scenario: Two veto, one abstain

- **WHEN** two owners respond "veto" and one responds "abstain"
- **THEN** resolution is "vetoed", reason is "abstain-to-majority"

### Requirement: Unanimous rule for high-value assets

The system SHALL require all non-abstaining owners to approve before resolving as "approved" whenever the decision description references a top-3 KTC-valued roster player or any future 1st-round pick. "Unanimous" means all three owners respond "approve"; a single "veto" blocks the decision regardless of the others.

A top-3 roster player is determined at resolution time by: loading `cache/sleeper.json` rosters, loading `cache/ktc.json` player values, ranking our team's (roster_id=2) rostered players by KTC value descending, and checking whether any player whose normalized name appears in the decision description is among the top 3.

A future 1st-round pick is detected when the decision description contains the pattern "1st" (case-insensitive) and any of "2026", "2027", "2028", or "pick".

If neither cache is available, the system SHALL default to requiring unanimous approval (safe fallback).

#### Scenario: Description references a top-3 player, two approvals, one veto

- **WHEN** the decision involves a top-3 roster player and one owner vetoes
- **THEN** resolution is "vetoed" (unanimous not met); majority rule does NOT apply

#### Scenario: Description references a 1st-round pick, all three approve

- **WHEN** the decision involves a future 1st-round pick and all owners approve
- **THEN** resolution is "approved" with reason noting unanimous approval of protected asset

#### Scenario: Both caches unavailable

- **WHEN** neither `cache/sleeper.json` nor `cache/ktc.json` exists at resolution time
- **THEN** the system applies unanimous rule as a safe fallback and records reason as "unanimous (cache unavailable)"

### Requirement: Resolution fields written to decisions.json

The system SHALL write `resolution` and `resolution_reason` fields to each entry in `data/decisions.json`. For entries that cannot yet resolve, `resolution` SHALL be "pending" and `resolution_reason` SHALL list which owners have not yet responded. The write SHALL be atomic.

#### Scenario: Resolution computed for all entries on each run

- **WHEN** `resolve_decisions.py` runs
- **THEN** every entry in `data/decisions.json` has a `resolution` field after the run, and already-resolved entries are not recomputed (their `resolution` is preserved)

#### Scenario: Entry already resolved

- **WHEN** an entry already has a non-pending `resolution` field
- **THEN** the system does not overwrite it; a resolved decision is immutable
