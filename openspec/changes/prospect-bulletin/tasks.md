## 1. Scaffolding

- [x] 1.1 Create `data/consensus_board.json` as an empty JSON array `[]`; add a sibling `data/consensus_board_schema.md` documenting the fields: `name` (string), `position` (string), `school` (string), `consensus_rank` (int), `source` (string, optional)
- [x] 1.2 Add `CFBD_API_KEY` to the list of required secrets in `README.md` or a secrets reference doc (or create one if none exists); do NOT hardcode the key anywhere

## 2. Prospect Stats Script

- [x] 2.1 Create `scripts/sync_prospects.py`; at startup read `CFBD_API_KEY` from the environment — exit non-zero with a clear message if it is absent; load `config.yaml` to read `cfbd_season` if present, otherwise fall back to `datetime.now().year`
- [x] 2.2 Call `GET https://api.collegefootballdata.com/stats/player/season?year={year}&seasonType=regular` with Bearer auth and a 15-second timeout; on any HTTP or network error, print a descriptive error to stderr and exit non-zero leaving any existing `cache/prospects.json` untouched
- [x] 2.3 Parse the response: pivot the denormalized rows (one row per player+stat category) into per-player dicts keyed by `(playerId, team)`; collect `receivingYards`, `receivingTD`, `receivingReceptions`, `rushingYards`, `rushingCarries`, `passingYards`, `passingCompletions`, `passingAttempts` — use `.get()` with 0 defaults so missing categories do not raise
- [x] 2.4 Filter to skill positions only (WR, TE, RB, QB) using the `statType` or player position field in the response; discard all other positions
- [x] 2.5 Compute the dynasty composite score for each player using the formula from design.md: `score = (yards_per_game_norm × POSITION_WEIGHT) × efficiency_factor × AGE_FACTOR`; define all formula constants (`GAMES_PLAYED_NORM`, `POSITION_WEIGHTS`, `EFFICIENCY_BASE`, `AGE_FACTOR`) as named module-level constants; include each component value in the output alongside the final score
- [x] 2.6 Assign `stat_rank` (1 = highest composite score) after sorting; write `cache/prospects.json` atomically via `tempfile.mkstemp` + `os.replace()` with fields: `player`, `team`, `position`, `composite_score`, `stat_rank`, `yards_per_game`, `efficiency_factor`, `age_factor`, `season`, `last_updated`
- [x] 2.7 Smoke-test: run `python scripts/sync_prospects.py` (requires `CFBD_API_KEY` in environment); verify `cache/prospects.json` has at least 30 entries, all have `stat_rank`, and `last_updated` is present; inspect the top 5 entries by score

## 3. Consensus Script

- [x] 3.1 Create `scripts/sync_consensus.py`; read `data/consensus_board.json`; if the file is missing, print a descriptive message and exit non-zero; if the parsed list is empty, print a warning and exit non-zero without overwriting any existing `cache/consensus.json`
- [x] 3.2 Sort entries by `consensus_rank` ascending; resolve ties by secondary sort on `name` alphabetically; write `cache/consensus.json` atomically with the sorted list plus a `last_updated` ISO 8601 UTC timestamp
- [x] 3.3 Smoke-test: add 3 sample entries to `data/consensus_board.json`; run `python scripts/sync_consensus.py`; verify `cache/consensus.json` is written with correct sort order and `last_updated` present; restore `data/consensus_board.json` to `[]` after verifying

## 4. Bulletin Generator

- [x] 4.1 Create `scripts/generate_bulletin.py`; if `cache/prospects.json` is missing, write `site/bulletin.md` with a placeholder message ("Prospect data unavailable -- run python scripts/sync_prospects.py first") and exit 0
- [x] 4.2 If `cache/consensus.json` is present, load it; if missing, proceed with stat-rank-only mode and set a flag to include a note on the bulletin page that consensus data is absent
- [x] 4.3 Merge the two lists by normalized player name (lowercase, strip punctuation, collapse spaces — same normalization as `analyze_trade.py`); players in only one source get `null` for the missing rank; players in neither are excluded
- [x] 4.4 Select top 15–20 entries: sort by `min(stat_rank, consensus_rank)` where both are present, or the single available rank; include all entries tied at the 15th rank up to a max of 20
- [x] 4.5 Compute divergence for each entry where both ranks are numeric: if `abs(consensus_rank - stat_rank) > DIVERGENCE_THRESHOLD` (default 5), build the divergence note string; define `DIVERGENCE_THRESHOLD` as a named constant
- [x] 4.6 Write `site/bulletin.md` (create `site/` if needed): H1 "Prospect Bulletin", one row per selected entry showing position, school, stat rank, consensus rank, and divergence note (if any); include a stale-cache warning line if either cache's `last_updated` is more than 8 days old; add a `_Last updated: {ISO timestamp}_` footer
- [x] 4.7 Smoke-test: add 20+ sample entries to `data/consensus_board.json` and re-run `sync_consensus.py`; run `generate_bulletin.py`; inspect `site/bulletin.md` — verify H1 present, at least 15 entries, at least one divergence flag if the sample data includes a rank gap > 5, and last-updated footer; restore `data/consensus_board.json` to `[]` after verifying

## 5. GitHub Actions

- [x] 5.1 Create `.github/workflows/prospect.yml` with a `0 8 * * 1` cron (Monday 08:00 UTC) and `workflow_dispatch`; steps: checkout, setup-python 3.12, pip install, `sync_prospects.py`, `sync_consensus.py`, `generate_bulletin.py`, then commit and push `cache/prospects.json cache/consensus.json site/bulletin.md` with `[skip ci]`; pass `CFBD_API_KEY: ${{ secrets.CFBD_API_KEY }}` as an env var on the sync_prospects step only
- [x] 5.2 Verify `requirements.txt` already includes `requests` and `pyyaml` (both used by the new scripts); add any missing deps with pinned versions; do not add the `cfbd` PyPI package (not used — we call the API directly)
