## Why

Co-owners currently have no in-tool way to move a logged decision from "recorded" to "resolved" — every vote still ends in a group text to confirm consensus. This feature closes that gap by adding resolution logic on top of the existing decision-log data, and extends the same mechanism to weekly lineup consensus, where a stalled decision is worse because games actually start.

## What Changes

- New script `scripts/resolve_decisions.py` reads `data/decisions.json`, computes resolution status for every entry using majority or unanimous rules (per asset type), writes `resolution` and `resolution_reason` fields back into each entry, and auto-resolves overdue lineup entries as "auto-approved by deadline"
- `scripts/log_decision.py` gains a new entry type (`lineup`) and a new mode (3 — propose lineup) that captures a deadline timestamp and proposed starting lineup alongside the standard propose/respond flow; the respond flow (mode 2) is unchanged
- `scripts/generate_decision_summary.py` is updated to surface `resolution` status — pending decisions in a prominent block, resolved decisions showing outcome, lineup entries showing deadline
- `data/decisions.json` gains two new optional fields per entry: `resolution` (pending / approved / vetoed / abstained-to-majority / auto-approved) and `resolution_reason` (human-readable explanation of how it resolved)
- `.github/workflows/publish.yml` gains a `resolve_decisions.py` step that runs before the summary generation step, so every push to decisions.json triggers automatic resolution computation

## Capabilities

### New Capabilities

- `vote-resolution`: Resolution logic layer — majority (2/3) for standard decisions; unanimous required when any top-3 KTC-valued roster player or any future 1st-round pick is involved; abstain-to-majority when exactly one owner abstains and the other two agree; status field written back to decisions.json
- `lineup-consensus`: New `lineup` entry type with a `deadline` ISO timestamp and a `proposed_lineup` list; deadline-based auto-resolution if outstanding responses remain when the deadline passes; flagged distinctly from genuine consensus in the log

### Modified Capabilities

- `decision-log`: Entry schema gains optional `resolution`, `resolution_reason`, `deadline`, and `proposed_lineup` fields; `generate_decision_summary.py` renders resolution status; `log_decision.py` gains lineup entry type and propose-lineup mode

## Impact

- `data/decisions.json`: backward-compatible schema additions (optional fields)
- `scripts/log_decision.py`: new mode added; existing modes 1 and 2 unchanged
- `scripts/generate_decision_summary.py`: updated rendering for resolution status
- `scripts/resolve_decisions.py`: new script, reads KTC and Sleeper caches for top-3 check
- `.github/workflows/publish.yml`: one new step before existing generate step
- No new API calls, no new secrets, no new dependencies beyond what is already in requirements.txt

## Non-goals

- Time-based auto-resolution for transaction decisions (only lineup entries auto-resolve at deadline)
- Push notifications or Slack/SMS alerts when a decision resolves
- Quorum rules beyond 3 owners (hardcoded to the current co-owner group)
- Editing or deleting logged entries
