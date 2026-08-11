## 1. Configuration

- [x] 1.1 Add a `team_mode` mapping to `config.yaml` — one entry per owner keyed by owner name, with values `contending`, `retooling`, or `rebuilding` (e.g., `team_mode: {LWFuller: retooling, MooSo: retooling, blakecbishop: retooling}`); owners can update their own value to reflect current team stance

## 2. KTC Sync Script

- [x] 2.1 Create `scripts/sync_ktc.py`; identify and verify the KTC public JSON endpoint URL (the community-used undocumented endpoint at `https://keeptradecut.com/dynasty-rankings?format=2` or equivalent); hardcode as a constant `KTC_URL`
- [x] 2.2 Implement HTTP GET with a 30-second timeout; on non-2xx response or network error, print a descriptive error to stderr including stale cache's `last_updated` if it exists, and exit non-zero without overwriting `cache/ktc.json`
- [x] 2.3 Parse the response JSON: extract player entries (`player_name`, `position`, `team`, `value`) and pick entries (`pick_label`, `value`); handle unexpected schema changes with a descriptive parse error
- [x] 2.4 Add `name_key` field to each player entry: lowercase, strip all punctuation, collapse multiple spaces to single space
- [x] 2.5 Write atomically to `cache/ktc.json` via `tempfile.mkstemp` + `os.replace()`; include `players` list, `picks` list, and `last_updated` ISO 8601 UTC timestamp
- [x] 2.6 Smoke-test: run `python scripts/sync_ktc.py`, inspect `cache/ktc.json` — verify `players` entries have `name_key`, `picks` list is populated with at least one entry, and `last_updated` is present

## 3. Trade Evaluator Script

- [x] 3.1 Create `scripts/analyze_trade.py`; at startup, load `config.yaml` (owners list, team_mode map) and verify `cache/ktc.json` and `cache/sleeper.json` both exist — exit non-zero with a message naming which file is missing and which sync script to run
- [x] 3.2 Check `cache/ktc.json` staleness: if `last_updated` is more than 48 hours old, print a warning with the timestamp but continue
- [x] 3.3 Implement owner-selection prompts for Side A and Side B (numbered list, accepts number or exact name, re-prompts on invalid); the two sides must be different owners
- [x] 3.4 Implement asset-entry loop for each side: prompt for a player name or pick label; normalize input; look up in `ktc.json` players by `name_key` match; on no match, print the normalized input, show the 5 closest `name_key` matches as suggestions, and re-prompt; allow user to enter empty line to finish adding assets to that side; for picks, if typed label doesn't match, display the full `picks` list with numbers and let user select by number
- [x] 3.5 Compute raw value totals (sum of `value` for each side); calculate absolute differential and percentage skew toward the higher side; determine verdict label: `"approximately even"` if within 1%, otherwise `"favors [owner]"`
- [x] 3.6 Apply team-mode pick-weight multipliers to picks using the *receiving* owner's `team_mode`: `REBUILD_WEIGHT = 1.20`, `RETOOL_WEIGHT = 1.05`, `CONTEND_WEIGHT = 0.85`; recompute adjusted totals and adjusted differential; if `team_mode` is missing for an owner, default to 1.0 and flag it in the verdict
- [x] 3.7 Cross-reference the receiving owner's roster: look up all player IDs on their roster in `cache/sleeper.json` via `player_metadata`; count players at the same position as each acquired player; if count ≥ 2, add a consideration flag: `"[owner] already has [N] rostered [POS]"`
- [x] 3.8 Print the structured verdict: Side A total (raw), Side B total (raw), adjusted differential, favored side, and up to 2 consideration flags (team-mode note if multiplier applied, positional redundancy if flagged)
- [x] 3.9 After printing, prompt: `"Log this trade to the decision log? (y/N)"` — if yes, write a new entry to `data/decisions.json` atomically: `type=trade`, `proposer=Side A owner`, description summarizing the trade assets, rationale containing the verdict text, all other owners set to `pending`, proposer set to `approve`; print confirmation
- [x] 3.10 Smoke-test: run `python scripts/analyze_trade.py` with a known trade (e.g., one rostered player vs. a pick); verify the printed differential matches manual calculation; test the pick-weight path by temporarily setting one owner to `rebuilding`; opt in to decision-log and verify the new entry in `data/decisions.json`

## 4. GitHub Actions

- [x] 4.1 Add `python scripts/sync_ktc.py` as a step in `.github/workflows/sync.yml`, after the Sleeper sync step; add `cache/ktc.json` to the `git add` line in the commit step alongside `cache/sleeper.json` and `cache/news.json`
