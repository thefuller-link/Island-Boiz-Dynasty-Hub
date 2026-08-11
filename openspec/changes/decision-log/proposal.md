## Why

Priority feature: **#1 — Decision log** (highest priority).

There is no record of why our team made any given move. Trades get proposed and discussed in Discord, waiver claims happen, and within a week nobody remembers who vetoed what or what the reasoning was. Without a persistent log, the trade analysis engine and any future retrospective have nothing to build on.

## What Changes

- New script `scripts/log_decision.py` — an interactive CLI that prompts an owner through the fields of a new decision entry (type, description, their response, optional rationale) and appends a formatted JSON entry to `data/decisions.json`.
- New script `scripts/generate_decision_summary.py` — reads `data/decisions.json` and renders a Markdown summary (`site/decisions.md` or equivalent) showing recent entries and any entries still awaiting a response from one or more owners.
- New data file `data/decisions.json` — the append-only log, committed to the repo so git history serves as the audit trail.
- GitHub Actions workflow updated (or new workflow added) to run `generate_decision_summary.py` on push so the static site always reflects the latest log state.

## Capabilities

### New Capabilities

- `decision-entry`: The schema and append behavior for a single decision log entry — fields, valid values, and the constraint that entries are append-only (never edited in place).
- `decision-input`: The interactive CLI that collects a new entry from an owner and writes it to the log without requiring manual JSON editing.
- `decision-summary`: The read path — querying the log and rendering a human-readable summary of recent decisions and pending responses.

### Modified Capabilities

*(none — no existing spec-level behavior changes)*

## Impact

- **New files**: `scripts/log_decision.py`, `scripts/generate_decision_summary.py`, `data/decisions.json` (or `data/.gitkeep`), `site/decisions.md` (generated)
- **Dependencies**: no new external packages beyond Python stdlib (`json`, `datetime`, `pathlib`) — no additions to `requirements.txt`
- **APIs**: none — entirely local, no network calls
- **Free-tier API implications**: none
- **Git**: `data/decisions.json` is committed to the repo intentionally; it is source data, not a build artifact

## Non-goals

- No voting mechanism — that is a separate priority #5 feature.
- No automated ingestion from Sleeper — decisions are manual human records.
- No editing or deleting past entries — append-only is the invariant.
- No authentication or access control — all three owners share the same repo access.
- No rich UI — plain Markdown output is sufficient for this change.
