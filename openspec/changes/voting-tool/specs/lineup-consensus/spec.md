## Purpose

Extends the decision-log with a lineup entry type that captures a proposed weekly starting lineup, uses the same approve/veto/abstain mechanism as transaction decisions, and auto-resolves to the proposed lineup if outstanding responses remain when the deadline passes.

## ADDED Requirements

### Requirement: Lineup entry type

The system SHALL support a `lineup` entry type in `data/decisions.json`. A lineup entry SHALL include a `deadline` field (ISO 8601 UTC timestamp) representing the latest time owners can respond before auto-resolution, and a `proposed_lineup` field (list of player names or Sleeper player IDs representing the proposed starters).

#### Scenario: Lineup entry created

- **WHEN** an owner logs a new lineup entry via `log_decision.py`
- **THEN** the resulting entry has `type: "lineup"`, a `deadline` timestamp, and a `proposed_lineup` list; responses default to "pending" for all non-proposing owners

#### Scenario: Lineup entry missing deadline

- **WHEN** a lineup entry is created without a deadline
- **THEN** the system rejects it with a clear error; a lineup entry without a deadline cannot auto-resolve

### Requirement: Lineup deadline derivation

The system SHALL compute the lineup deadline as the earlier of: (a) a user-supplied offset (e.g., "2 hours before kickoff"), or (b) the earliest game lock time for the current NFL week from `cache/sleeper.json` `nfl_state` minus a configurable buffer (default: 2 hours). If `nfl_state` is unavailable, the system SHALL require the user to enter the deadline manually.

#### Scenario: NFL state available in cache

- **WHEN** `cache/sleeper.json` contains `nfl_state.season_type: "regular"` and game lock data
- **THEN** `log_decision.py` suggests a deadline 2 hours before the first game of the week; the user may confirm or override

#### Scenario: NFL state unavailable

- **WHEN** `cache/sleeper.json` is missing or `nfl_state` does not contain lock time data
- **THEN** `log_decision.py` prompts the user to enter a deadline manually in a recognizable date-time format

### Requirement: Deadline-based auto-resolution

When `resolve_decisions.py` runs and a lineup entry's `deadline` has passed with at least one response still "pending", the system SHALL set `resolution` to "auto-approved" and `resolution_reason` to "auto-resolved by deadline — not all owners responded". The proposed lineup is considered adopted as-is.

#### Scenario: Deadline passed, one owner still pending

- **WHEN** the current time exceeds the entry's `deadline` and one owner has not responded
- **THEN** resolution is "auto-approved" with a reason clearly stating the deadline was reached

#### Scenario: All owners responded before deadline

- **WHEN** all three owners responded before the deadline and a majority approved
- **THEN** resolution is "approved" (standard majority rule), not "auto-approved"

#### Scenario: Lineup vetoed before deadline

- **WHEN** two or more owners veto the lineup before the deadline
- **THEN** resolution is "vetoed"; the deadline auto-resolution path is NOT taken

### Requirement: Deadline visibility on the decisions page

The system SHALL render lineup entries with their deadline timestamp prominently. An upcoming deadline within 12 hours SHALL be flagged as "deadline approaching" on the page. A passed deadline SHALL be shown as "deadline passed — awaiting resolution".

#### Scenario: Lineup entry with upcoming deadline

- **WHEN** a lineup entry's deadline is within 12 hours of now
- **THEN** `site/decisions.md` shows a "deadline approaching" notice alongside the entry

#### Scenario: Lineup entry with past deadline, not yet resolved

- **WHEN** a lineup entry's deadline has passed but `resolve_decisions.py` has not yet run
- **THEN** `site/decisions.md` shows "deadline passed — awaiting resolution" rather than treating it as normal pending
