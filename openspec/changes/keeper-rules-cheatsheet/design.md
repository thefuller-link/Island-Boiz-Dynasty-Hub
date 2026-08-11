## Context

See proposal.md for motivation. The existing sync workflow (`sync.yml`) already calls several Sleeper endpoints and commits JSON caches; this change adds one more call (`GET /league/{league_id}`) in the same job. The `/league/{league_id}` endpoint returns the full league object including `scoring_settings`, `roster_positions`, `settings` (which contains `max_keepers`, `trade_deadline`, `waiver_type`, etc.) — all publicly accessible, no auth required.

Data flow:

```
Sleeper API (/v1/league/{id})
    |
    v
sync_league_settings.py --> cache/league_settings.json
                                    |
                      generate_rules_page.py <-- data/league_rules_extra.json
                                    |
                              site/rules.md
                                    |
                          .github/workflows/sync.yml
```

## Goals / Non-Goals

**Goals:**
- One-time fetch of league settings per sync cycle, cached as JSON
- Rules page renders meaningfully when either source is absent
- Keeper section present only when Sleeper settings actually encode keepers
- Clear visual separation between auto-pulled and manually-maintained content

**Non-goals:**
- No server-side rendering or dynamic page updates
- No diff/alert when league settings change between runs
- No editor UI for `league_rules_extra.json` — plain file edited via git

## Decisions

### Cache the full Sleeper league object, render selectively

**Decision:** `sync_league_settings.py` writes the entire `/league/{id}` response to `cache/league_settings.json` without filtering. `generate_rules_page.py` selects what to display.

**Rationale:** Storing the full object avoids re-fetching if we later want additional fields (e.g., `trade_deadline` wasn't initially rendered but the data is already cached). The cache is small (<10 KB) and the extra fields are harmless. Filtering at the sync layer would require a re-sync to pick up newly-rendered fields.

**Alternative considered:** Store only the fields we render — rejected because it couples the sync script to the presentation layer and makes adding new displayed fields require a two-step deploy (sync change + page change).

### No stale fallback in sync script; generator handles missing cache gracefully

**Decision:** `sync_league_settings.py` exits non-zero on API failure and does not write a stale file. `generate_rules_page.py` renders a placeholder when the cache is absent.

**Rationale:** League settings change very rarely. A sync failure is a transient error that will self-heal on the next cron run (every 6 hours). Unlike player news — where stale data has time value — league settings are binary: either current or absent. A placeholder on the page is clearer than silently showing data that's potentially weeks old from a retry.

**Alternative considered:** Write a stale fallback — rejected because a one-run failure leaves the cache intact from the previous successful run anyway; only a complete cold start has no cache, and the placeholder handles that.

### `data/league_rules_extra.json` schema: array of rule objects

**Decision:** The supplementary file stores rules as a JSON array of `{rule, category}` objects plus top-level `last_updated` and `last_updated_by` fields.

```json
{
  "last_updated": "2026-08-07",
  "last_updated_by": "LWFuller",
  "rules": [
    {"category": "General", "rule": "No tanking for draft picks."},
    {"category": "Keeper", "rule": "Keeper cost is the round above where a player was drafted."}
  ]
}
```

**Rationale:** A structured array allows grouping by category in the rendered output. It's simple enough to edit by hand but structured enough to render with a loop. The `last_updated_by` field provides the attribution the spec requires without requiring git blame on the page.

**Alternative considered:** Plain Markdown file for the manual section — rejected because it can't be parsed for structured rendering (categories, timestamps) and would just be `cat`-ed into the output.

### Render Sleeper's `scoring_settings` as human-readable labels, not raw keys

**Decision:** Map the most common Sleeper scoring keys (`rec`, `rush_yd`, `pass_yd`, `pass_td`, etc.) to human-readable labels in a dict inside the generator. Unknown keys are rendered as-is with the raw Sleeper key name, so no settings are silently dropped.

**Rationale:** Sleeper scoring keys like `rec` and `rush_yd` are opaque to owners reading the page. The mapping dict covers the ~20 most common keys for a skill-position dynasty league; the fallback ensures new or uncommon settings still appear.

**Alternative considered:** Render all raw Sleeper keys — rejected; the output would be unreadable to a casual owner.

## Risks / Trade-offs

- **Sleeper field names change:** If Sleeper renames a settings key, the human-readable label mapping silently misses it and falls back to the raw key. The page stays functional but the label may be cryptic. Mitigated by the raw-key fallback being visible (not silent).
- **Keeper detection heuristic:** We infer "keeper league" by checking `settings.max_keepers > 0`. If Sleeper adds new keeper-mode fields outside `max_keepers`, the detection misses them. Low risk for our specific league; owners can override via `league_rules_extra.json`.
- **Manual file diverges from reality:** `league_rules_extra.json` requires a git commit to update. If owners forget to update it after a rule change, the page shows stale manual rules. Mitigated by the clear "manually maintained" label and last-updated attribution making the staleness visible.
