## 1. Repository Scaffolding

- [x] 1.1 Create `cache/.gitkeep` so the cache directory exists in the repo without committing data files
- [x] 1.2 Add `cache/sleeper.json` and `cache/news.json` to `.gitignore` (runtime output, not source) — or confirm they should be committed; see design.md Migration Plan
- [x] 1.3 Create `scripts/` directory if it does not exist
- [x] 1.4 Create `config.yaml` at the repo root with an empty `watchlist: []` key as a starter; document the expected format (list of player full names as strings)

## 2. Dependencies

- [x] 2.1 Add `requests`, `feedparser`, and `PyYAML` with pinned versions to `requirements.txt` (run `pip install requests feedparser PyYAML` locally, capture exact versions)
- [x] 2.2 Verify `requirements.txt` is committed and that a clean `pip install -r requirements.txt` succeeds

## 3. Sleeper Sync Script

- [x] 3.1 Create `scripts/sync_sleeper.py`; read `SLEEPER_LEAGUE_ID` from environment, exit with error message and non-zero code if unset
- [x] 3.2 Implement roster fetch: `GET https://api.sleeper.app/v1/league/{league_id}/rosters` with a 10-second timeout; parse response into a dict keyed by `owner_id`
- [x] 3.3 Implement matchup fetch: `GET https://api.sleeper.app/v1/league/{league_id}/matchups/{nfl_state_week}` (fetch current week from `GET https://api.sleeper.app/v1/state/nfl` first)
- [x] 3.4 Implement transactions fetch: `GET https://api.sleeper.app/v1/league/{league_id}/transactions/{nfl_state_week}`
- [x] 3.5 Implement trending-adds fetch: `GET https://api.sleeper.app/v1/players/nfl/trending/add?lookback_hours=24&limit=200` with a 10-second timeout; store the ordered list of player IDs under `trending_adds`
- [x] 3.6 Implement player-metadata fetch: `GET https://api.sleeper.app/v1/players/nfl` with a 30-second timeout (response is ~2 MB); for each player, retain only `player_id`, `full_name`, and `years_exp`; store under `player_metadata` keyed by `player_id`
- [x] 3.7 Implement stale fallback: wrap all HTTP calls in try/except; if any fail, log to stderr and exit non-zero without overwriting the existing cache file
- [x] 3.8 On success, write `cache/sleeper.json` with keys `rosters`, `matchups`, `transactions`, `trending_adds`, `player_metadata`, and `last_updated` (ISO 8601 UTC)
- [x] 3.9 Smoke-test locally: set `SLEEPER_LEAGUE_ID` and run `python scripts/sync_sleeper.py`; verify `cache/sleeper.json` contains all six keys with non-empty values

## 4. News Filter Script

- [x] 4.1 Create `scripts/sync_news.py`; load and validate `cache/sleeper.json` at startup — exit non-zero with a descriptive error identifying the missing key if `rosters`, `trending_adds`, or `player_metadata` is absent
- [x] 4.2 Build the four tier sets of player full names:
  - **rostered**: `full_name` values for all player IDs across every owner's roster (look up each ID in `player_metadata`)
  - **trending**: `full_name` values for all player IDs in `trending_adds` (look up each ID in `player_metadata`)
  - **rookie**: `full_name` values for all entries in `player_metadata` where `years_exp == 0`
  - **watchlist**: strings listed under `watchlist` in `config.yaml`; if the file is missing or has no `watchlist` key, default to an empty set without error
- [x] 4.3 Fetch RotoWire NFL RSS: use `requests.get(URL, timeout=10)` for the raw fetch, pass the response content to `feedparser.parse()`; wrap in try/except
- [x] 4.4 For each RSS entry, check (case-insensitive substring) whether any name from any tier appears in `entry.title` or `entry.summary`; collect all matching category labels into a `categories` list
- [x] 4.5 Retain only entries where `categories` is non-empty; discard the rest
- [x] 4.6 Implement stale fallback: if the RSS fetch fails, log to stderr and exit non-zero without overwriting `cache/news.json`
- [x] 4.7 On success, write `cache/news.json` with a top-level `items` array (each item with `title`, `description`, `published`, `link`, `categories`) and `last_updated` (ISO 8601 UTC)
- [x] 4.8 Smoke-test locally: ensure `cache/sleeper.json` exists and `config.yaml` has at least one watchlist entry; run `python scripts/sync_news.py`; spot-check that items appear under the expected categories and no non-tracked player items appear

## 5. GitHub Actions Workflow

- [x] 5.1 Create `.github/workflows/sync.yml` with a `schedule` trigger (`cron: '0 */6 * * *'`) and a `workflow_dispatch` trigger for manual runs
- [x] 5.2 Add a job with steps: checkout repo, set up Python (pin version), install from `requirements.txt`, run `sync_sleeper.py`, run `sync_news.py`
- [x] 5.3 Add a final step to commit and push updated cache files back to the repo (using `git config` + `git add cache/` + `git commit --allow-empty-message` pattern or `stefanzweifel/git-auto-commit-action`)
- [x] 5.4 Wire `SLEEPER_LEAGUE_ID` as a GitHub Actions secret (`${{ secrets.SLEEPER_LEAGUE_ID }}`); confirm the secret is set in the repo settings
- [x] 5.5 Trigger the workflow manually via `workflow_dispatch` and verify both cache files are written and committed, with `cache/news.json` items showing correct `categories` values
