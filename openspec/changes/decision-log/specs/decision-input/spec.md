## Purpose

An interactive command-line script with two modes: logging a new decision entry field-by-field, or recording a response to an existing entry on behalf of an owner who was absent when it was first logged. Both modes eliminate the need to hand-edit JSON and ensure every write is valid before it lands.

## ADDED Requirements

### Requirement: Present mode selection at startup
The script SHALL begin by asking the running owner which mode they want: (1) log a new decision, or (2) record my response to an existing entry. The owner SHALL be re-prompted if their input matches neither option.

#### Scenario: Owner selects new-entry mode
- **GIVEN** an owner runs `log_decision.py`
- **WHEN** they select the new-entry mode
- **THEN** the script proceeds to collect all required fields for a new entry

#### Scenario: Owner selects respond mode
- **GIVEN** an owner runs `log_decision.py`
- **WHEN** they select the respond mode
- **THEN** the script lists entries where that owner's response is still `pending` and prompts them to choose one

### Requirement: Prompt for all required fields in sequence
The script SHALL prompt the running owner for: entry type (from the constrained list), a plain-text description of the move, the running owner's own response (from the constrained list), and an optional rationale. It SHALL NOT require the other two owners' responses at entry time — their responses default to `pending`.

#### Scenario: Owner completes all prompts
- **GIVEN** an owner runs `log_decision.py`
- **WHEN** they provide valid values for type, description, and their own response
- **THEN** the script appends a valid entry to `data/decisions.json` and prints a confirmation message

#### Scenario: Rationale prompt is skippable
- **GIVEN** an owner reaches the rationale prompt
- **WHEN** they submit an empty response
- **THEN** the entry is written without a rationale and the script does not error

### Requirement: Validate constrained fields before writing
The script SHALL reject invalid values for `type` and `response` at the prompt stage, re-prompt with the list of valid options, and SHALL NOT write any entry until all constrained fields contain valid values.

#### Scenario: Invalid type is rejected and re-prompted
- **GIVEN** the type prompt is displayed
- **WHEN** the owner enters a value not in `[trade, waiver-claim, roster-move, other]`
- **THEN** the script displays the valid options and re-prompts without writing anything

#### Scenario: Invalid response is rejected and re-prompted
- **GIVEN** the response prompt is displayed
- **WHEN** the owner enters a value not in `[approve, veto, abstain]`
- **THEN** the script displays the valid options and re-prompts without writing anything

### Requirement: Identify the running owner
The script SHALL ask the owner to identify themselves by selecting from the list of three co-owner names configured in `config.yaml`. The selected owner is recorded as `proposer` and their response is recorded under their key in `responses`.

#### Scenario: Owner selects their identity
- **GIVEN** `config.yaml` lists three owner names
- **WHEN** the owner selects their name from the prompt
- **THEN** the entry's `proposer` field equals the selected name and `responses` contains their answer under that key

#### Scenario: Unknown owner name is rejected
- **GIVEN** the owner prompt is displayed
- **WHEN** a value not matching any configured owner name is entered
- **THEN** the script re-prompts without writing anything

### Requirement: Auto-generate id and date
The script SHALL auto-populate `id` (a unique string, e.g., ISO 8601 timestamp with millisecond precision) and `date` (today's date in ISO 8601 format). The owner SHALL NOT be prompted for these fields.

#### Scenario: Date is set to today automatically
- **GIVEN** an owner completes all prompts
- **WHEN** the entry is written
- **THEN** the `date` field equals the current UTC date in `YYYY-MM-DD` format

### Requirement: Atomic write — no partial entries
The script SHALL write the complete entry to `data/decisions.json` in a single operation. If the write fails (e.g., disk error), the file SHALL be left in its previous valid state; no partial entry SHALL be persisted.

#### Scenario: Write failure leaves file intact
- **GIVEN** `data/decisions.json` contains existing entries
- **WHEN** a disk error occurs during the write of a new entry
- **THEN** `data/decisions.json` retains its prior content and contains no partial entry

### Requirement: Respond mode — list pending entries for the running owner
In respond mode, after the owner identifies themselves, the script SHALL read `data/decisions.json` and display only the entries where that owner's response is currently `pending`, showing each entry's `id` (truncated for readability), `date`, `type`, and `description`. If no such entries exist, the script SHALL inform the owner and exit with code 0 without writing anything.

#### Scenario: Pending entries are shown for the owner
- **GIVEN** owner B's response is `pending` in two entries
- **WHEN** owner B selects respond mode and identifies themselves
- **THEN** the script displays those two entries and prompts owner B to select one

#### Scenario: No pending entries for the owner
- **GIVEN** owner A has already responded to every entry in the log
- **WHEN** owner A selects respond mode and identifies themselves
- **THEN** the script prints a message stating no entries are awaiting their response and exits with code 0

### Requirement: Respond mode — collect and validate the response
After the owner selects an entry, the script SHALL prompt for their response (`approve`, `veto`, or `abstain`), re-prompting on invalid input, then update that entry's `responses` field in `data/decisions.json` atomically. All other fields of the entry SHALL remain unchanged.

#### Scenario: Valid response is recorded
- **GIVEN** owner B selects an entry where their response is `pending`
- **WHEN** owner B enters `approve`
- **THEN** that entry's `responses.B` is updated to `approve` and all other entry fields are unchanged

#### Scenario: Already-responded entry is not offered
- **GIVEN** owner A has already responded `veto` to entry X
- **WHEN** owner A enters respond mode
- **THEN** entry X is not shown in the list of selectable entries

### Requirement: Exit with confirmation or error
After a successful write the script SHALL print a human-readable confirmation including the generated `id`. If an unrecoverable error occurs, the script SHALL print a descriptive error message and exit with a non-zero exit code.

#### Scenario: Success message shown after write
- **GIVEN** an owner completes all prompts with valid input
- **WHEN** the entry is written successfully
- **THEN** the script prints a confirmation that includes the new entry's `id`
