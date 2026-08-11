## 1. Dependency

- [x] 1.1 Add `nfl_data_py` to `requirements.txt`; pin the version by running `pip install nfl_data_py` locally (or in a temp env), capturing the version, and adding `nfl_data_py==<version>` plus any new transitive deps (`pandas`, `pyarrow`, etc.) that are not already pinned; commit the updated lockfile

## 2. Sync Script

- [x] 2.1 Create `scripts/sync_usage.py`; at startup load `config.yaml` and `cache/sleeper.json`; read `nfl_state.season_type` and current `season`; if season_type is not `"regular"`, log the season type, write a placeholder `cache/usage.json` with `{"season_type": "<value>", "data_note": "preseason -- not representative", "players": [], "last_updated": "<iso>"}`, and exit 0
- [x] 2.2 Build a `player_id -> metadata` index from `sleeper.json` `player_metadata`; build a `normalized_name -> player_id` lookup; filter to skill-position players with `years_exp` 0 or 1 to define the rookie scope set
- [x] 2.3 Call `nfl_data_py.import_weekly_rosters(years=[current_season])` with a try/except around the import; on exception, print a descriptive error to stderr and exit non-zero
- [x] 2.4 Filter the resulting DataFrame to rows where the player's normalized name (or GSIS ID where available) appears in the rookie scope set; extract `week`, `snap_pct`, `target_share`, `route_participation`, and `rz_targets` (proxy for red zone touches) per player per week; store null for absent fields, not 0
- [x] 2.5 Structure the output as a dict keyed by normalized player name, each value containing `player_name`, `position`, `weeks` (list of weekly records), `sleeper_id` (or null if unmatched); write atomically to `cache/usage.json` with `season_type`, `season`, `players`, and `last_updated` fields

## 3. Page Generator

- [x] 3.1 Create `scripts/generate_usage_page.py`; if `cache/usage.json` is missing or `players` is empty, write `site/usage.md` with a placeholder message and exit 0; if `data_note` is present in the cache, render it as a bold warning at the top of the page; if `last_updated` is more than 9 days ago, render a stale-data warning
- [x] 3.2 Implement `_normalize(text)`: identical normalization (lowercase, strip punctuation, collapse spaces) used in other scripts
- [x] 3.3 Implement `_classify_trajectory(values)`: takes a list of floats/Nones; filter to non-null values; if fewer than 2, return `"insufficient data"`; compare mean of last 2 vs mean of prior; return `"rising"`, `"falling"`, or `"flat"` based on 5-point threshold
- [x] 3.4 Load `cache/sleeper.json` rosters; build a set of normalized player names that are on any team's roster (iterate all rosters' `players` lists, resolve each player_id via `player_metadata` to full_name, normalize)
- [x] 3.5 Load `cache/prospects.json` and `cache/consensus.json` if they exist; build normalized-name -> stat_rank and normalized-name -> consensus_rank lookup dicts; skip silently if either file is absent
- [x] 3.6 Load `cache/news.json` if it exists; build a list of `{headline, published, items}` records; skip silently if absent
- [x] 3.7 Implement `_injury_flag(player_name, position, nfl_team, rising_week, news_records)`: scan news headlines published in the same NFL week as rising_week for an injury keyword ("injured", "out", "IR", "questionable") AND a name matching another player on the same NFL team at the same position; return a flag string or None
- [x] 3.8 For each player in `cache/usage.json`, classify snap trajectory and target trajectory; look up roster membership; look up college cross-reference; compute injury flag if trajectory is rising; assemble a player record: `{name, position, snap_trend, target_trend, is_free_agent, stat_rank, consensus_rank, injury_flag, weeks}`
- [x] 3.9 Render `site/usage.md`: open with any data_note/stale warnings; render a "## Rising Free Agents" section first (free-agent players with rising snap or target trajectory, sorted by snap trajectory value descending); render a "## Rostered Rookies" section; within each section render a Markdown table with columns: Player, Pos, Snap Trend, Target Trend, RZ Touches (last week), College Rank, Note; write atomically via tempfile + os.replace
- [x] 3.10 Smoke-test: run `python scripts/generate_usage_page.py` with the existing off-season placeholder cache; verify `site/usage.md` is written with the preseason data note and a "no rookies tracked" message; confirm no errors

## 4. GitHub Actions

- [x] 4.1 Create `.github/workflows/usage.yml`: trigger on `schedule` cron `0 9 * * *` (09:00 UTC daily) and `workflow_dispatch`; jobs: checkout, setup-python 3.12, `pip install -r requirements.txt`, `python scripts/sync_usage.py`, `python scripts/generate_usage_page.py`; commit `cache/usage.json site/usage.md` with `[skip ci]` message
- [x] 4.2 Confirm `nfl_data_py` and all its transitive deps are present in `requirements.txt` (from task 1.1); no runtime `pip install` in the workflow
