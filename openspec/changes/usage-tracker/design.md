## Context

See proposal.md for motivation. The existing hub already has parallel patterns to follow: `sync_prospects.py` fetches an external API, pivots per-player data, and writes an atomic JSON cache; `generate_bulletin.py` reads that cache plus `cache/consensus.json` and `cache/sleeper.json` to produce a static Markdown page. This feature reuses that exact pattern with nflverse as the data source.

The key constraint is that nflverse data is accessed via the `nfl_data_py` package, which downloads parquet files from a public GitHub-hosted CDN at runtime. This requires adding one new PyPI dependency and adds a download step to the CI job (files are ~1–3 MB per season, fetched on demand).

Data flow:

```
nflverse CDN (parquet)
    |
    v
sync_usage.py --> cache/usage.json
    |                    |
    |            generate_usage_page.py <-- cache/sleeper.json
    |                    |             <-- cache/prospects.json (optional)
    |                    |             <-- cache/consensus.json (optional)
    |                    |             <-- cache/news.json (optional)
    |                    v
    |             site/usage.md
    |
    v
.github/workflows/usage.yml (daily cron, season-gated)
```

## Goals / Non-Goals

**Goals:**
- Daily rookie usage snapshot during the active regular season
- Rising free-agent rookies surfaced at the top of the page as the primary call-to-action
- Preseason runs produce a labeled placeholder, not misleading data
- Graceful fallback when optional cross-reference caches are absent

**Non-goals:**
- No multi-season historical tracking
- No per-player detail pages or drill-downs
- No backend server — all output is static Markdown
- No LLM narrative generation
- No veteran usage tracking

## Decisions

### nfl_data_py for nflverse access

**Decision:** Use `nfl_data_py` (the official Python client for nflverse) to fetch weekly participation data via `nfl_data_py.import_weekly_rosters()` or `import_pbp_participation()`. This downloads parquet from nflverse's public GitHub CDN.

**Rationale:** No API key required, no rate limit, no auth. The library handles parquet parsing and returns a pandas DataFrame. The data is authoritative and free. The alternative — fetching raw parquet URLs directly with `requests` and parsing with `pyarrow` — saves the `nfl_data_py` abstraction but requires maintaining raw URLs that change each season.

**Alternative considered:** Scraping ESPN or NFL.com for snap data — rejected; both require scraping fragile HTML and violate ToS risk. nflverse is explicitly public-use.

### Season-gate via sleeper.json nfl_state

**Decision:** Read `nfl_state.season_type` from `cache/sleeper.json` rather than computing season dates from a hardcoded config. If the field is missing, treat as off-season (safe default).

**Rationale:** Sleeper already tracks season state and `sync_sleeper.py` commits it to the cache on its own schedule. Reusing that source keeps season detection in one place and avoids duplicating a config value. The downside is that `cache/sleeper.json` must be present and fresh; if it's stale by more than a week, the season-gate may be wrong — but that scenario also means other features are already running on stale data, so it's not unique to this script.

**Alternative considered:** Add `season_start` / `season_end` dates to `config.yaml` — rejected; requires manual updates each year and creates a second source of truth.

### Trajectory classification: last-2 vs. prior average

**Decision:** Classify trajectory by comparing the mean of the player's last 2 non-null snap % values against the mean of any earlier non-null values. Threshold: >5 percentage points difference = rising/falling; within 5 = flat. Minimum 2 non-null values required before any classification.

**Rationale:** Simple, transparent, and appropriate for the 3–4 week window in a dynasty context. A threshold-based label is more useful than a slope coefficient for owners skimming a weekly page. The 5-point threshold filters out noise from garbage-time fluctuations.

**Alternative considered:** Linear regression slope — more accurate but harder to reason about and overkill for 3–4 data points.

### Injury correlation: keyword scan of news.json headlines

**Decision:** Scan `cache/news.json` for headlines containing an injury keyword ("injured", "out", "IR", "questionable") AND a player name that appears in the same NFL team's roster as the tracked rookie. The week of the headline is inferred from `published` timestamp (parsed to the nearest NFL week using the nfl_state `week` and `season`).

**Rationale:** news.json already exists and is updated daily. The correlation is heuristic and may produce false positives (e.g., "out" appearing in a non-injury context), but the risk is a spurious flag rather than a missed opportunity — owners will still verify before making a claim. The cost of a false negative (missing a real opportunity) outweighs the cost of a false positive.

**Alternative considered:** Structured depth-chart API (e.g., FantasyPros or ESPN) — rejected; free-tier access requires registration and the data is available informally through the news feed already.

### Roster cross-reference: normalized name matching against player_metadata

**Decision:** Match nflverse player names against Sleeper `player_metadata` full names using the same normalization function used in other scripts (lowercase, strip punctuation, collapse spaces). A player is rostered if their normalized name matches any player_id in any roster's `players` list.

**Rationale:** nflverse and Sleeper use slightly different name formats; normalization handles common cases (apostrophes, periods, Jr./Sr. suffixes). The same function is already proven in `analyze_trade.py`, `sync_ktc.py`, and `generate_bulletin.py`. Exact-match without normalization would miss too many players.

**Alternative considered:** Match on a shared player ID (e.g., GSIS ID) — nflverse has GSIS IDs but Sleeper uses its own player_id system; no reliable cross-walk is available without a separate mapping table.

### workflow: daily cron with [skip ci] commit

**Decision:** `usage.yml` runs on a daily cron (`0 9 * * *` UTC, shortly after nflverse's own daily refresh). It commits `cache/usage.json` and `site/usage.md` with `[skip ci]` to avoid triggering other workflows.

**Rationale:** Consistent with `prospect.yml` and `sync.yml` patterns already in the repo.

## Risks / Trade-offs

- **nflverse CDN availability:** nflverse data is hosted on GitHub and is occasionally delayed or unavailable. `sync_usage.py` will catch HTTP errors and exit non-zero, failing the GitHub Actions step visibly. No stale-fallback is used for the nflverse fetch because stale usage data is misleading rather than merely incomplete.
- **nfl_data_py dependency size:** The package pulls pandas and pyarrow as transitive dependencies, which are large (~50 MB combined). CI install time will increase. Pinning versions in requirements.txt mitigates version drift.
- **Name normalization false matches:** A common first name without a last name, or a player with an identical normalized name to another, could produce a wrong roster match. Risk is low given the rookie-only scope reduces the player pool significantly.
- **Preseason noise:** If `nfl_state.season_type` flips to "regular" before nflverse has populated regular-season data, the script may ingest week-1 data that is a hybrid of preseason and regular season. The `data_note` field mitigates this for the first week.
