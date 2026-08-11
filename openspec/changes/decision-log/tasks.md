## 1. Configuration and Scaffolding

- [x] 1.1 Add an `owners` key to `config.yaml` listing the three co-owner display names as a YAML list (e.g., `owners: ["Alice", "Bob", "Charlie"]`)
- [x] 1.2 Create `data/decisions.json` as an empty JSON array `[]` and commit it; this is source data, not a build artifact, so it is not gitignored
- [x] 1.3 Create `site/` directory with a `.gitkeep` if it does not already exist (this is where generated Markdown output lands)

## 2. Decision Input Script

- [x] 2.1 Create `scripts/log_decision.py`; at startup, load `config.yaml` and read the `owners` list — exit with a descriptive error if the file is missing or `owners` is absent
- [x] 2.2 Implement mode-selection prompt at startup: display two options ("1. Log new decision", "2. Record my response"), re-prompt on invalid input, then branch to the appropriate flow
- [x] 2.3 **New-entry flow** — owner-selection prompt: display numbered list of owner names, accept a number or exact name, re-prompt on invalid; store selection as `proposer`
- [x] 2.4 **New-entry flow** — type prompt: display the four valid types (`trade`, `waiver-claim`, `roster-move`, `other`), accept input, re-prompt on invalid
- [x] 2.5 **New-entry flow** — description prompt: accept any non-empty free-text string; re-prompt if blank
- [x] 2.6 **New-entry flow** — response prompt: display `approve`, `veto`, `abstain`, accept input, re-prompt on invalid; store under the selected owner's key in `responses`; set all other owners to `pending`
- [x] 2.7 **New-entry flow** — optional rationale prompt: accept free-text or empty; store as `rationale` (omit the key if empty)
- [x] 2.8 **New-entry flow** — auto-generate `id` (ISO 8601 UTC timestamp with milliseconds) and `date` (today's UTC date, `YYYY-MM-DD`); implement atomic write via temp file + `os.replace()`
- [x] 2.9 **Respond flow** — owner-selection prompt (same as 2.3); after selection, filter `data/decisions.json` to entries where that owner's `responses` value is `pending`; if none, print a message and exit 0
- [x] 2.10 **Respond flow** — display the filtered pending entries with a short label (truncated `id`, `date`, `type`, `description`); prompt owner to select one by number; re-prompt on invalid input
- [x] 2.11 **Respond flow** — response prompt (same validation as 2.6); update only the selected owner's key in the chosen entry's `responses` object; all other entry fields remain unchanged; write atomically via temp file + `os.replace()`
- [x] 2.12 Print a confirmation message after any successful write; on unrecoverable error print a descriptive message and exit non-zero
- [x] 2.13 Smoke-test new-entry flow: run `log_decision.py`, select mode 1, complete all prompts, verify entry in `data/decisions.json` with correct `pending` values for the other two owners
- [x] 2.14 Smoke-test respond flow: run `log_decision.py`, select mode 2, identify as a different owner, select the entry from 2.13, record a response, verify only that owner's `responses` key changed

## 3. Decision Summary Script

- [x] 3.1 Create `scripts/generate_decision_summary.py`; load `data/decisions.json` — if the file is missing or contains an empty array, write a "no decisions logged yet" placeholder to `site/decisions.md` and exit 0
- [x] 3.2 If `data/decisions.json` exists but is not valid JSON, print a descriptive error and exit non-zero without touching `site/decisions.md`
- [x] 3.3 Sort entries newest-first by the `date` field
- [x] 3.4 Render a "Recent Decisions" Markdown section: show the 10 most recent entries, each with date, type, proposer, description, and a per-owner response table row
- [x] 3.5 Render a "Pending Responses" Markdown section: list any entries where at least one owner's response is `pending`, naming the specific owner(s) still outstanding; if none, write "No decisions are currently awaiting a response."
- [x] 3.6 Write the complete Markdown output to `site/decisions.md`, overwriting any prior file
- [x] 3.7 Smoke-test: with at least one entry in `data/decisions.json` (use the one from task 2.10), run `python scripts/generate_decision_summary.py` and inspect `site/decisions.md` for correct content and pending highlighting

## 4. GitHub Actions Workflow

- [x] 4.1 Add a new GitHub Actions workflow (or a new job in an existing one) triggered by `push` to the default branch; its only step after checkout and Python setup is `python scripts/generate_decision_summary.py`
- [x] 4.2 Add a subsequent step that commits and pushes `site/decisions.md` back to the repo if the file changed (reuse the same git-auto-commit pattern from the sync workflow, or use `stefanzweifel/git-auto-commit-action`)
- [ ] 4.3 Trigger the workflow manually (push a test commit) and verify `site/decisions.md` is generated and committed correctly; confirm the pending section reflects the current state of `data/decisions.json`
