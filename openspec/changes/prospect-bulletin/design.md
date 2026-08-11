## Context

Three new single-purpose scripts join the pipeline. `sync_prospects.py` calls the CFBD API and writes scored player data; `sync_consensus.py` validates and stages a manually-maintained big board; `generate_bulletin.py` merges both and writes `site/bulletin.md`. A new `prospect.yml` workflow triggers on Monday mornings, independent of the daily `sync.yml`.

See proposal.md for motivation.

Data flow:

```
CFBD API (/stats/player/season) --> sync_prospects.py -----+
data/consensus_board.json       --> sync_consensus.py -----+--> cache/*.json --> generate_bulletin.py --> site/bulletin.md
```

CFBD API key is stored as GitHub Actions secret `CFBD_API_KEY`; no key is ever hardcoded. Sleeper's API needs no key. Both are consistent with the existing auth pattern.

## Goals / Non-Goals

**Goals:**
- Fetch skill-position season stats from CFBD in a single API call (within free-tier budget)
- Compute a transparent, documented composite score with named constants
- Merge with a manually-maintained consensus board; support a live-pull upgrade later
- Render a bulletin-style Markdown page updated weekly

**Non-goals:**
- Age-adjusted scoring in MVP (requires per-player roster API calls that would exceed the 1,000/month free-tier budget at scale; the formula structure reserves the age-penalty factor but defaults it to 1.0)
- Full scouting profiles or LLM-generated narrative (separate future feature)
- Real-time or per-user refresh
- NFL usage stats (nflverse) — college players only

## Decisions

### CFBD API access: direct `requests` calls over the `cfbd` Python library

**Decision:** Use `requests` with Bearer token auth directly against the CFBD REST API rather than the `cfbd` PyPI package.

**Rationale:** The `cfbd` package wraps the same REST endpoints but adds a generated client with many unused dependencies. The rest of the project uses `requests` for all external calls; consistency matters more than convenience wrappers for a single endpoint.

**Alternative considered:** `cfbd` PyPI package — rejected to keep the dependency footprint minimal and consistent.

### Single CFBD endpoint: `/stats/player/season`

**Decision:** Call `GET /stats/player/season?year={year}&seasonType=regular` once per run. This returns all tracked stat categories for all players in a single response.

**Rationale:** The CFBD endpoint returns denormalized rows (one per player+category). A single call covers the full season for all teams. At one call per week for ~5 months of college football season, total usage is ~20 calls/month — well inside the 1,000/month free-tier limit.

**Alternative considered:** Per-team roster calls to get class year for age penalty — rejected because 130+ FBS teams × 1 call each = 130 calls per run, compressing the monthly budget significantly with minimal MVP benefit.

### Composite score formula: volume × efficiency, age factor reserved at 1.0

**Decision:** Score = (yards_per_game_normalized × position_weight) × efficiency_factor × age_factor, where `age_factor = 1.0` in MVP.

Formula constants (all named, top of script):

| Constant | Value | Meaning |
| --- | --- | --- |
| `GAMES_PLAYED_NORM` | 12 | Typical FBS regular season games, for per-game normalization |
| `POSITION_WEIGHTS` | WR=1.0, TE=0.95, RB=0.80, QB=0.70 | Dynasty positional scarcity adjustment |
| `EFFICIENCY_BASE` | 10.0 | Yards-per-target/carry divisor for efficiency factor |
| `AGE_FACTOR` | 1.0 | Placeholder; override per-player via `data/prospect_ages.json` in future |
| `DIVERGENCE_THRESHOLD` | 5 | Minimum rank gap to flag divergence |

Efficiency factor = min(yards_per_opportunity / EFFICIENCY_BASE, 1.5) to cap outliers.

**Alternative considered:** Weighted multi-factor regression — rejected as over-engineered for a bulletin heuristic; named constants are more transparent and auditable.

### Consensus source: manually-updated `data/consensus_board.json`

**Decision:** `sync_consensus.py` reads `data/consensus_board.json` (committed to the repo) and stages it as `cache/consensus.json`. No live scrape in MVP.

**Rationale:** Public dynasty big boards (DynastyProcess, DynastyNerds) do not expose a stable, free, unauthenticated JSON endpoint. Scraping HTML is fragile and violates most sites' ToS. A manually-maintained JSON file is reliable, auditable, and can be updated by any co-owner via a PR. The spec leaves the door open for a live-pull upgrade by keeping `sync_consensus.py` as the abstraction layer.

**Alternative considered:** DynastyProcess CSV export — checked; requires login as of 2024, not scriptable on free tier.

### Separate workflow `prospect.yml`, Monday 08:00 UTC

**Decision:** Run `prospect.yml` independently from `sync.yml` on a `0 8 * * 1` cron (Monday 08:00 UTC, after Sunday college games).

**Rationale:** College football runs on weekends; prospect stats update meaningfully after Saturday games. Running on the same schedule as the daily/6-hour roster sync would waste API quota during weekdays when nothing has changed. Separation also means a CFBD API failure doesn't block the roster-news sync.

**Alternative considered:** Add steps to `sync.yml` — rejected to keep each workflow focused on one cadence and one failure domain.

### Player name matching: normalize then exact-match, with unmatched tolerance

**Decision:** Normalize names (lowercase, strip punctuation, collapse spaces) before matching `cache/prospects.json` to `cache/consensus.json`. Unmatched players from either source are included with a null rank for the missing side.

**Rationale:** Consistent with name matching already used in `analyze_trade.py` and `sync_ktc.py`. Null-rank tolerance keeps the bulletin useful even when source coverage differs.

## Risks / Trade-offs

- **CFBD API schema changes:** The `/stats/player/season` response format has changed before (V1 → V2 migration). If CFBD restructures the response, `sync_prospects.py` will fail with a descriptive error and leave the stale cache intact. Low probability mid-season; mitigated by explicit field access with `.get()` defaults.
- **Consensus board staleness:** A manually-updated file can drift from the actual consensus. The `last_updated` timestamp on the bulletin page makes staleness visible. Owners can update `data/consensus_board.json` via PR.
- **CFBD free-tier quota:** 1,000 calls/month; the weekly run uses ~1 call. Plenty of headroom for future enhancements (e.g., per-team roster calls for age data).
- **CFBD season gap:** During the NFL offseason (Feb–Aug), no current college season stats exist. `sync_prospects.py` should fall back to the prior year's cached data rather than returning an empty set.

## Open Questions

- Should the prior-year CFBD season be shown in the off-season with a clear label, or should the bulletin show a placeholder? (Decision deferred — either is acceptable; the stale-cache fallback already handles this naturally via `last_updated` timestamp visibility.)
