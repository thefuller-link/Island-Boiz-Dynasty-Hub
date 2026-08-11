## 1. Scaffolding

- [x] 1.1 Create `data/pick_overrides.json` as an empty JSON array `[]`; add a comment block at the top of the file (or a sibling `pick_overrides_schema.md`) documenting each field: `year` (string), `round` (int), `original_owner` (display name), `current_owner` (display name), `note` (string), `uncertain` (bool)

## 2. Pick Sync Script

- [x] 2.1 Create `scripts/sync_picks.py`; at startup load `config.yaml` (league_id, owners) and verify `cache/sleeper.json` and `cache/ktc.json` both exist — exit non-zero with a message naming which file is missing and which sync script to run
- [x] 2.2 Build a `roster_id → display_name` reverse index: iterate `cache/sleeper.json` `rosters` (keyed by user_id, each with a `roster_id` integer), cross-reference with `user_map` (user_id → display_name), and store as a dict for lookups during pick derivation
- [x] 2.3 Determine the pick year window: read the NFL state season year from `cache/sleeper.json` (from `nfl_state.season` if stored, else fall back to `datetime.now().year`); generate default picks for `year` through `year + 2`, rounds 1–4, with each team owning all its own picks (90 default pick slots total for a 10-team league across 3 years × 3 rounds; LWFuller/MooSo/blakecbishop are co-managers of one team, roster_id=2)
- [x] 2.4 Fetch `/v1/league/{id}/traded_picks` from the Sleeper API with a 10-second timeout; on any HTTP or network error, print a descriptive error to stderr and exit non-zero; this call is non-cacheable (no stale fallback) since it is the authoritative source for the sync
- [x] 2.5 Apply the traded_picks response to the default ledger: for each entry, set `current_owner` to the resolved display name for `roster_id`, record `original_owner` from `owner_id`, set `provenance` to `"via [original_owner]"` when they differ, and set `uncertain: true` for any entry whose `owner_id` or `roster_id` cannot be resolved to a display name
- [x] 2.6 Match each pick to KTC values from `cache/ktc.json`: try exact `pick_label` match (e.g., "2027 Mid 1st" label from KTC); if no exact match, try the "Mid" tier label for the same year + round (e.g., construct "2027 Mid 1st" for a round-1 pick); if still no match, try "Early" then "Late"; record `value_source` as `"ktc_exact"`, `"ktc_mid_default"`, `"ktc_early_default"`, `"ktc_late_default"`, or `"unmatched"` accordingly
- [x] 2.7 Load `data/pick_overrides.json` (if it exists; skip silently if missing); for each override entry match on `year` + `round` + `original_owner` and apply its `current_owner`, `note`, `uncertain` fields to the corresponding pick in the ledger; if no match exists (override refers to a pick not in the ledger), add it as a new entry with `source: "manual"`
- [x] 2.8 Write `cache/picks.json` atomically via `tempfile.mkstemp` + `os.replace()`; include `picks` array (fields: `year`, `round`, `label`, `ktc_label`, `original_owner`, `current_owner`, `provenance`, `value`, `value_source`, `uncertain`, `note`, `source`) and `last_updated` ISO 8601 UTC timestamp
- [x] 2.9 Smoke-test: run `python scripts/sync_picks.py`; inspect `cache/picks.json` — verify `picks` spans 3 years × 3 rounds × 10 teams = 90 base picks (minus any merged overrides), at least some picks have non-null `value`, `last_updated` is present, and `uncertain` is `false` for all standard picks

## 3. Picks Page Script

- [x] 3.1 Create `scripts/generate_picks_page.py`; if `cache/picks.json` is missing or its `picks` array is empty, write `site/picks.md` with a placeholder message ("No pick data available — run `python scripts/sync_picks.py` first") and exit 0
- [x] 3.2 Load `config.yaml` for the owners list; for each owner, filter picks where `current_owner == owner` and sort by year then round; render an H2 section per owner with a Markdown table (columns: Pick, Value, Provenance, Flag); if an owner holds no picks, add a "No future picks" row; mark uncertain picks with `[?]` in the Flag column and include the note
- [x] 3.3 Render a `## Full League` section: all picks across all owners sorted by year then round, with columns: Pick, Owner, Value, Provenance, Flag; format value as the integer if non-null or "N/A" if null; include provenance text only when `current_owner != original_owner`
- [x] 3.4 Add a footer line to `site/picks.md`: `_Last updated: {last_updated from cache/picks.json}_`
- [x] 3.5 Write `site/picks.md` (create `site/` directory if needed); print a confirmation line with entry count
- [x] 3.6 Smoke-test: run `python scripts/generate_picks_page.py`; inspect `site/picks.md` — verify per-owner H2 sections exist for all three owners, at least one pick shows a numeric value, the full-league table appears, and the last-updated footer is present

## 4. GitHub Actions

- [x] 4.1 Add `python scripts/sync_picks.py` as a step in `.github/workflows/sync.yml`, after the KTC sync step and before the news sync step; add `cache/picks.json` and `site/picks.md` to the `git add` line in the commit step alongside the other cache files
- [x] 4.2 Add `python scripts/generate_picks_page.py` as a step in `.github/workflows/sync.yml`, immediately after the sync_picks step (picks page is data-driven by the sync, not by a manual push); the picks page is committed alongside the picks cache in the same step as task 4.1
