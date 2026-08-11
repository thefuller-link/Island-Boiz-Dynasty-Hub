## Purpose

Defines the schema and persistence contract for a single decision log entry — the atomic unit of record in the decision log that captures what was proposed, by whom, and how each owner responded. Core fields are immutable once written; the `responses` field is updatable as owners register their stance over time.

## ADDED Requirements

### Requirement: Entry schema
Every decision log entry SHALL contain the following fields: `id` (unique string, auto-generated), `date` (ISO 8601 date string), `type` (one of: `trade`, `waiver-claim`, `roster-move`, `other`), `proposer` (owner identifier string), `description` (non-empty plain-text string), `responses` (an object with one key per owner, each value one of: `approve`, `veto`, `abstain`, `pending`), and `rationale` (optional string, may be empty or absent).

#### Scenario: Complete entry has all required fields
- **GIVEN** a new entry is appended to `data/decisions.json`
- **WHEN** that entry is read back
- **THEN** it contains `id`, `date`, `type`, `proposer`, `description`, and `responses` fields, and the `type` value is one of the four valid types

#### Scenario: Rationale field is optional
- **GIVEN** an owner logs a decision without providing a rationale
- **WHEN** the entry is written to `data/decisions.json`
- **THEN** the entry is valid and the `rationale` field is either absent or an empty string

### Requirement: Response values are constrained
The `responses` object SHALL contain exactly one key per owner (the three co-owners are fixed). Each value SHALL be one of `approve`, `veto`, `abstain`, or `pending`. `pending` is the default for any owner who has not yet responded.

#### Scenario: Unresponded owners default to pending
- **GIVEN** an entry is created by owner A with owner A's response recorded
- **WHEN** the entry is written
- **THEN** owners B and C have `"pending"` as their response value

#### Scenario: All three owners' responses are present
- **GIVEN** a fully resolved decision
- **WHEN** the entry is read from `data/decisions.json`
- **THEN** the `responses` object has exactly three keys, one per owner

### Requirement: Core fields are immutable
Once written to `data/decisions.json`, an entry's `id`, `date`, `type`, `proposer`, and `description` fields SHALL NOT be changed by any script or tool. These fields represent the original record of what was proposed and by whom.

#### Scenario: New entry does not alter prior core fields
- **GIVEN** an entry exists in `data/decisions.json`
- **WHEN** a new entry is appended
- **THEN** the prior entry's `id`, `date`, `type`, `proposer`, and `description` fields are byte-for-byte identical to what was originally written

### Requirement: Responses field is updatable
An owner's individual response within an existing entry's `responses` object MAY be updated from `pending` to a final value (`approve`, `veto`, or `abstain`) after initial entry. Only the `responses` field of an existing entry may change; all other fields remain immutable. An owner's response SHALL NOT be changed once it is set to a final value.

#### Scenario: Absent owner records response after initial entry
- **GIVEN** owner B's response is `pending` in an existing entry
- **WHEN** owner B runs the script and selects that entry to respond to
- **THEN** owner B's response in that entry is updated to their chosen value and all other fields in the entry are unchanged

#### Scenario: Already-responded owner cannot overwrite their response
- **GIVEN** owner A's response is `approve` in an existing entry
- **WHEN** owner A attempts to record a response for that same entry
- **THEN** the script informs owner A they have already responded and does not modify the entry

### Requirement: Log file is a JSON array
`data/decisions.json` SHALL be a valid JSON file containing a single top-level array of entry objects. If the file does not exist when the first entry is appended, it SHALL be created with that entry as the sole element of the array.

#### Scenario: File created on first entry
- **GIVEN** `data/decisions.json` does not exist
- **WHEN** a new entry is appended
- **THEN** `data/decisions.json` is created as a valid JSON array containing exactly one entry

#### Scenario: Subsequent entries accumulate
- **GIVEN** `data/decisions.json` already contains N entries
- **WHEN** a new entry is appended
- **THEN** `data/decisions.json` contains N + 1 entries and all prior entries are unchanged
