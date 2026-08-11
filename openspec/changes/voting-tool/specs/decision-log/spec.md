## MODIFIED Requirements

### Requirement: Decision entry schema

The `data/decisions.json` entry schema is extended with four optional fields. Existing entries without these fields SHALL continue to load and render without error; the fields are additive and backward-compatible.

New optional fields:
- `resolution`: string, one of "pending" | "approved" | "vetoed" | "abstained-to-majority" | "auto-approved". Written by `resolve_decisions.py`; absent on entries that have never been processed.
- `resolution_reason`: string, human-readable explanation of how the resolution was reached. Written alongside `resolution`.
- `deadline`: ISO 8601 UTC timestamp string. Present only on `lineup` entries.
- `proposed_lineup`: list of strings (player names or Sleeper player IDs). Present only on `lineup` entries.

#### Scenario: Legacy entry without resolution fields

- **WHEN** `data/decisions.json` contains an entry with no `resolution` field
- **THEN** `generate_decision_summary.py` renders it as "pending" without error

#### Scenario: Entry with resolution field set

- **WHEN** an entry has `resolution: "approved"`
- **THEN** `generate_decision_summary.py` renders it in the resolved section with the resolution reason visible

### Requirement: Decisions page shows resolution status

`generate_decision_summary.py` SHALL render a "Pending" section (decisions awaiting responses or resolution), an "Approved" section, and a "Vetoed / Blocked" section. Each pending entry SHALL show which specific owners have not yet responded. Each resolved entry SHALL show the resolution reason.

#### Scenario: Pending decisions surfaced first

- **WHEN** `data/decisions.json` contains a mix of pending and resolved entries
- **THEN** `site/decisions.md` leads with the pending section and all pending entries appear there with "Waiting on: [owner list]" noted

#### Scenario: Resolved entries grouped by outcome

- **WHEN** entries have `resolution: "approved"` or `resolution: "vetoed"`
- **THEN** they appear in distinct Approved / Vetoed sections, each showing the resolution reason

### Requirement: log_decision.py supports lineup entry type

`log_decision.py` SHALL present `lineup` as a selectable entry type (mode 1: log new decision). When selected, the script SHALL additionally prompt for: a `deadline` (with suggestion from nfl_state if available) and a `proposed_lineup` (space or comma-separated player list). All other modes (mode 2: respond) are unchanged.

#### Scenario: Owner selects lineup type in mode 1

- **WHEN** an owner chooses "lineup" as the entry type
- **THEN** the script prompts for deadline and proposed lineup before writing the entry

#### Scenario: Owner records response in mode 2 on a lineup entry

- **WHEN** a lineup entry appears in an owner's pending queue
- **THEN** the respond flow is identical to a transaction entry; no special handling required
