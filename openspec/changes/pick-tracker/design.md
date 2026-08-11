## Context

Two new single-purpose scripts join the existing pipeline. `sync_picks.py` derives pick ownership and writes `cache/picks.json`; `generate_picks_page.py` reads it and writes `site/picks.md`. Both follow the same conventions as the existing sync/generate pairs already in the repo.

**How Sleeper exposes pick ownership:** The Sleeper API has a dedicated endpoint `/v1/league/{id}/traded_picks` that returns all picks that have changed hands in the league as a flat list — no transaction replay needed. Each entry has `season` (year), `round`, `roster_id` (current owner), `previous_owner_id`, and `owner_id` (original owner), all expressed as roster IDs. Picks not in this list are still owned by their original team.

**Roster ID → display name resolution:** `cache/sleeper.json` stores `rosters` keyed by Sleeper user_id; each roster object contains `roster_id` (integer). `user_map` (added in trade-analysis-engine) maps user_id → display_name. Resolving a roster_id to a display name requires scanning rosters to find the matching user_id, then looking up user_map. `sync_picks.py` builds this reverse index at startup.

Data flow:

```
Sleeper API (/traded_picks) → sync_picks.py ─┐
cache/sleeper.json (user_map, rosters)        ├─→ cache/picks.json → generate_picks_page.py → site/picks.md
cache/ktc.json (pick values)                  │
data/pick_overrides.json (manual)            ─┘
```

## Goals / Non-Goals

**Goals:**
- Derive current pick ownership without replaying all transactions
- Attach KTC value (defaulting to "Mid" tier for unclassified picks)
- Allow manual override for picks Sleeper can't cleanly express
- Render per-team and full-league views in `site/picks.md`

**Non-goals:**
- Backend server or database (out-of-scope per project architecture)
- Automatic conditional pick resolution
- DEVY or IDP picks
- Real-time value refresh at page-load time

## Decisions

### Live Sleeper fetch in sync_picks.py rather than extending sync_sleeper.py

**Decision:** `sync_picks.py` calls `/traded_picks` directly rather than adding it to `sync_sleeper.py`.

**Rationale:** `sync_sleeper.py` is an already-applied, tested script. Adding another endpoint to it risks regressions and violates the single-purpose convention. `sync_picks.py` can reuse `_load_league_id()` logic via config.yaml and handle its own error path. The two scripts run in the same GitHub Actions job so timing is not an issue.

**Alternative considered:** Modify `sync_sleeper.py` — rejected to avoid touching already-verified code and to keep scripts single-purpose.

### Pick year window: current year + 2

**Decision:** Track picks for `current_year` through `current_year + 2` (3 seasons). Determine `current_year` from `cache/sleeper.json`'s NFL state, or fall back to the calendar year.

**Rationale:** Dynasty leagues typically value 2-3 years of picks in trade discussions. Beyond 3 years, values are highly speculative and the KTC data thins out. Three years covers all meaningful trade decisions.

**Alternative considered:** Fixed window (e.g., 2025–2028) — rejected because it requires manual updating each year.

### KTC value matching: "Mid" tier default for untiered picks

**Decision:** For picks where only year + round is known (no Early/Mid/Late tier), match against the "Mid" tier label from KTC (e.g., "2027 Mid 1st"). If no Mid exists, try Early, then Late, then mark as unmatched.

**Rationale:** "Mid" represents the median expectation for an unknown pick. The KTC data itself uses Early/Mid/Late tiers to represent draft position ranges; "Mid" is the most neutral default. The `value_source` field distinguishes a confident match from this fallback.

**Alternative considered:** Show a range (Early...Late values) — adds complexity to the output schema and makes the KTC matching logic significantly more involved for marginal benefit.

### pick_overrides.json: simple JSON array, hand-editable

**Decision:** `data/pick_overrides.json` is a JSON array of objects with `year`, `round`, `original_owner`, `current_owner`, `note`, and `uncertain` fields. It is committed to the repo and edited manually.

**Rationale:** The override file handles only edge cases (conditionals, Sleeper data gaps). A simple JSON array is readable without tooling and can be committed as normal source. No YAML or TOML needed — owners can add entries following the pattern already set by `decisions.json`.

**Alternative considered:** YAML — rejected because JSON is already the repo's data format (decisions.json, all caches).

### Rounds tracked: 1–4

**Decision:** Track rounds 1 through 4 for each year. Dynasty leagues commonly run 4-round startup drafts and annual rookie drafts.

**Rationale:** Most dynasty leagues use 4 rounds for rookie drafts. Rounds 5+ are rarely traded or referenced in dynasty context.

## Risks / Trade-offs

- **Sleeper traded_picks lag**: The `/traded_picks` endpoint may not reflect very recent same-session trades until the next sync. This is acceptable — the same stale-cache pattern applies as to all other Sleeper data.
- **KTC tier mismatch**: A "Mid" default may over- or under-value picks near the Early/Late boundary. The `value_source: "mid_default"` field lets callers detect this case and the page can annotate it.
- **Conditional picks**: Sleeper's API does not expose conditional pick logic. These are flagged as uncertain and handled by override. If conditionals resolve between syncs they will remain stale until the sync runs or an override is added.

## Open Questions

_(none — all decisions are resolvable before coding)_
