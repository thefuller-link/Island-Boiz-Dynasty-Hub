## 1. Scaffolding

- [x] 1.1 Add `"lineup"` to `VALID_TYPES` in `scripts/log_decision.py`; verify existing `data/decisions.json` entries without `resolution`, `deadline`, or `proposed_lineup` fields still load and round-trip without error (a quick `json.load` check is sufficient)

## 2. Resolution Script

- [x] 2.1 Create `scripts/resolve_decisions.py`; load `config.yaml` for the owners list and `data/decisions.json`; if `decisions.json` is missing or empty, print a message and exit 0; add a module-level constant `OWNERS` derived from config and `REQUIRED = len(OWNERS)` (3)
- [x] 2.2 Implement `_is_resolved(entry)`: return True if `entry.get("resolution")` is set and not "pending"; resolved entries are immutable and SHALL be skipped without modification
- [x] 2.3 Implement `_majority_resolution(responses, owners)`: count approvals and vetoes; if approvals >= 2 return ("approved", reason); if vetoes >= 2 return ("vetoed", reason); else return ("pending", waiting_list); handle abstain-to-majority: if exactly one owner abstains and the remaining two agree, resolve on their votes with reason "abstain-to-majority"
- [x] 2.4 Implement `_load_top3_players()`: load `cache/sleeper.json` and `cache/ktc.json`; find roster_id=2's player_ids from sleeper rosters; look up each player_id in ktc players by normalized name; sort by KTC value descending; return the top-3 normalized names; if either cache is missing return None (signals safe fallback to unanimous)
- [x] 2.5 Implement `_requires_unanimous(description, top3_names)`: normalize the description; if top3_names is None return True (safe fallback); return True if any top-3 name is a substring of the normalized description OR if the description matches the 1st-round pick pattern (contains "1st" AND at least one of "2026", "2027", "2028", "pick"); return False otherwise
- [x] 2.6 Implement `_unanimous_resolution(responses, owners)`: return ("approved", "unanimous") if all owners respond "approve"; return ("vetoed", reason) if any owner vetoes; else return ("pending", waiting_list)
- [x] 2.7 Implement deadline auto-resolution for lineup entries: if `entry.get("type") == "lineup"` and entry has a `deadline` field, and the deadline (parsed as ISO 8601 UTC) is in the past, and any owner is still "pending", set resolution to "auto-approved" with reason "auto-resolved by deadline — not all owners responded"
- [x] 2.8 Wire up main resolution loop: for each non-resolved entry, check deadline auto-resolution first (lineup entries only); then compute `_requires_unanimous` to choose majority vs unanimous path; set `entry["resolution"]` and `entry["resolution_reason"]`; write decisions.json atomically via `tempfile.mkstemp` + `os.replace()`
- [x] 2.9 Smoke-test: add a second test entry to `data/decisions.json` with all three owners set to "approve"; run `python scripts/resolve_decisions.py`; verify both entries now have a `resolution` field, the all-approve entry is "approved", the existing mixed entry remains "pending" (LWFuller:approve, MooSo:veto, blakecbishop:pending cannot resolve); inspect decisions.json

## 3. Lineup Entry in log_decision.py

- [x] 3.1 Add a helper `_suggest_lineup_deadline()` to `log_decision.py`: read `cache/sleeper.json` for `nfl_state`; if `season_type == "regular"`, compute the upcoming Sunday at 18:00 UTC (NFL 1pm ET kickoff) minus 2 hours = 16:00 UTC and return it as a formatted ISO string with a "(suggested)" label; if unavailable return None
- [x] 3.2 In `new_entry_flow`, when `entry_type == "lineup"`: call `_suggest_lineup_deadline()` and display the suggestion if available; prompt the user to confirm or enter their own deadline in "YYYY-MM-DD HH:MM UTC" format; parse and store as ISO 8601 UTC string in `entry["deadline"]`
- [x] 3.3 In `new_entry_flow`, when `entry_type == "lineup"`: after the deadline prompt, ask "Proposed starters (comma-separated player names or Sleeper IDs):"; split on commas, strip whitespace, store as `entry["proposed_lineup"]` list; require at least one entry
- [x] 3.4 Smoke-test: run `python scripts/log_decision.py`, choose mode 1, select "lineup", enter a deadline and a short proposed lineup; verify `data/decisions.json` contains the new entry with `type: "lineup"`, `deadline`, and `proposed_lineup` fields; then delete the test entry to restore clean state

## 4. Decision Summary Rendering

- [x] 4.1 Add a `RESOLUTION_LABEL` dict to `generate_decision_summary.py`: `{"approved": "APPROVED", "vetoed": "VETOED", "abstained-to-majority": "APPROVED (abstain-to-majority)", "auto-approved": "AUTO-APPROVED (deadline)", "pending": "pending"}`; update `render()` to use it
- [x] 4.2 Split the current single list in `render()` into three sections: "## Awaiting Response" (entries with `resolution` absent or "pending"), "## Approved" (entries with `resolution` in approved set), "## Vetoed / Blocked" (entries with `resolution == "vetoed"`); show `resolution_reason` on each resolved entry
- [x] 4.3 In the Awaiting Response section, for lineup entries with a deadline: if deadline is within 12 hours, add "(deadline approaching)" tag; if deadline has passed but entry is still pending add "(deadline passed — awaiting resolution)"; show the deadline timestamp for all lineup entries
- [x] 4.4 Smoke-test: construct a `data/decisions.json` with entries covering all four resolution states (pending, approved, vetoed, auto-approved) plus a lineup entry with a future deadline; run `python scripts/generate_decision_summary.py`; inspect `site/decisions.md` — verify all three H2 sections appear, the lineup entry shows its deadline, and resolution reasons are visible; restore `data/decisions.json` to the single original test entry afterward

## 5. GitHub Actions

- [x] 5.1 In `.github/workflows/publish.yml`, add a `python scripts/resolve_decisions.py` step immediately before the existing `generate_decision_summary.py` step; this ensures every push to `data/decisions.json` triggers resolution before the page is regenerated
- [x] 5.2 Confirm no new Python packages are required (`resolve_decisions.py` uses only `json`, `os`, `sys`, `tempfile`, `datetime`, `re`, and `yaml` — all already in requirements.txt or stdlib); no lockfile change needed
