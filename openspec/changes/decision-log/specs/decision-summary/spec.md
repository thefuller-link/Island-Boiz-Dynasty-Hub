## Purpose

Reads the decision log and renders a human-readable Markdown summary of recent entries and any decisions still awaiting a response from one or more owners, suitable for inclusion in the static site.

## ADDED Requirements

### Requirement: Render recent decisions
The script SHALL read `data/decisions.json` and render the most recent entries (up to a configurable limit, defaulting to 10) as a Markdown section listing each entry's date, type, proposer, description, and the current response from each owner.

#### Scenario: Recent entries appear in output
- **GIVEN** `data/decisions.json` contains at least one entry
- **WHEN** `generate_decision_summary.py` runs
- **THEN** the output Markdown contains a section showing recent decisions with date, type, proposer, description, and per-owner responses

#### Scenario: Entries are ordered newest-first
- **GIVEN** `data/decisions.json` contains multiple entries with different dates
- **WHEN** the summary is generated
- **THEN** the most recent entry appears first in the output

### Requirement: Highlight pending decisions
The script SHALL render a dedicated section listing any entries where at least one owner's response is still `pending`. Each entry in this section SHALL show which specific owner(s) have not yet responded.

#### Scenario: Pending entry appears in the pending section
- **GIVEN** an entry exists where owner B's response is `pending`
- **WHEN** the summary is generated
- **THEN** the pending section lists that entry and identifies owner B as having not yet responded

#### Scenario: No pending section when all decisions are resolved
- **GIVEN** all entries in `data/decisions.json` have non-`pending` responses for every owner
- **WHEN** the summary is generated
- **THEN** the pending section is either absent or explicitly states that no decisions are awaiting a response

### Requirement: Graceful empty-log handling
If `data/decisions.json` does not exist or contains an empty array, the script SHALL produce a valid Markdown file with a message indicating no decisions have been logged yet, rather than erroring or producing empty output.

#### Scenario: Missing log file produces placeholder output
- **GIVEN** `data/decisions.json` does not exist
- **WHEN** the summary script runs
- **THEN** a Markdown file is written containing a human-readable "no decisions logged yet" message, and the script exits with code 0

#### Scenario: Empty log array produces placeholder output
- **GIVEN** `data/decisions.json` exists but contains an empty array
- **WHEN** the summary script runs
- **THEN** a Markdown file is written containing a human-readable "no decisions logged yet" message

### Requirement: Output written to a fixed path
The script SHALL write its Markdown output to a fixed, configured path (e.g., `site/decisions.md`) so the GitHub Actions build step can reliably include it in the static site. The output SHALL be overwritten on each run.

#### Scenario: Output file is created or overwritten
- **GIVEN** the summary script runs successfully
- **WHEN** the output path already exists from a prior run
- **THEN** the file at that path is replaced with the current run's output

### Requirement: Non-zero exit on unreadable log
If `data/decisions.json` exists but cannot be parsed as valid JSON, the script SHALL exit with a non-zero exit code and a descriptive error message. It SHALL NOT write or overwrite the output summary file in this case.

#### Scenario: Corrupt log file does not overwrite output
- **GIVEN** `data/decisions.json` contains malformed JSON
- **WHEN** the summary script runs
- **THEN** the script exits with a non-zero code and the existing summary file (if any) is left unchanged
