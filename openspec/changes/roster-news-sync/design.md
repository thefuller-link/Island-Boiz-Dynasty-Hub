## Context

See `proposal.md` — Why for motivation. Current state: no data pipeline exists. The repo is a clean slate; the only established constraint is GitHub Actions + GitHub Pages (static output only) and a JSON-file cache pattern as the persistence layer.

Data flow for this change:

```
Sleeper REST API ──► scripts/sync_sleeper.py ──► cache/sleeper.json
                                                         │
RotoWire RSS Feed ──► scripts/sync_news.py ─────────────┘──► cache/news.json
                       (reads roster player list
                        from cache/sleeper.json)
```

Both scripts are invoked by a GitHub Actions workflow on a schedule. No static page generation in this change — the cache files are the only output.

## Goals / Non-Goals

**Goals:**
- Establish the `cache/` JSON schema that downstream features (trade analysis, rookie tracker, decision log) can depend on.
- Ensure both scripts are independently runnable (useful for local debugging) as well as composable in sequence within a workflow.
- Guarantee the site never serves a broken state: old cache is always preferable to no cache.

**Non-Goals:**
- Parsing or transforming data beyond the minimum needed to filter news to roster players — no analysis.
- Generating any HTML or static site output.
- Fetching player metadata beyond what is already embedded in Sleeper's roster endpoint.

## Decisions

### Two scripts, not one

**Decision**: `sync_sleeper.py` and `sync_news.py` are separate scripts.

**Rationale**: The Sleeper sync has no dependencies; the news sync depends on a current `cache/sleeper.json` to know which players are on rosters. Keeping them separate means each can fail independently, be retried independently, and be reasoned about in isolation. A monolithic sync script would create hidden ordering dependencies inside a single file.

**Alternative considered**: One orchestrator script calling both. Rejected because it violates the single-purpose convention and complicates retry logic in GitHub Actions (a failed step can be re-run without re-fetching Sleeper data if they are separate jobs/steps).

### `cache/` directory committed, `.gitkeep` only

**Decision**: Commit `cache/.gitkeep` so the directory exists in the repo; actual JSON cache files are written at runtime by the workflow.

**Rationale**: GitHub Actions checks out a clean repo. Without the directory present, the script would need to `mkdir -p cache` before writing — adding procedural boilerplate. A committed `.gitkeep` keeps scripts simpler.

**Alternative considered**: Scripts create `cache/` if absent. Acceptable but mixes directory management with data fetching; `.gitkeep` is idiomatic and cheaper.

### `feedparser` for RSS, `requests` for all HTTP

**Decision**: Use `feedparser` to parse the RotoWire RSS feed; use `requests` (with an explicit timeout) for all HTTP calls including the Sleeper REST API.

**Rationale**: `feedparser` handles RSS edge cases (encoding, malformed dates) so `sync_news.py` doesn't have to. `requests` is the de-facto standard for synchronous HTTP in Python and supports per-call timeouts cleanly.

**Alternative considered**: `urllib.request` (stdlib). Avoids an external dependency but requires manual timeout plumbing and has a worse API. Given we already need `feedparser`, adding `requests` adds negligible complexity.

### Player name matching strategy

**Decision**: Filter RSS items by checking if any Sleeper player's display name appears as a substring (case-insensitive) in the item's title or description.

**Rationale**: Sleeper's player objects include a `full_name` field that matches how players are typically named in sports news copy. Substring matching is fast, stateless, and needs no external lookup.

**Trade-off**: This can produce false positives for common names (e.g., a player named "Chase" matching "Patrick Mahomes in the Chase for MVP"). Acceptable for a dynasty hub with a small roster; a more precise approach (named-entity recognition) is out of scope for the free-tier static build.

### GitHub Actions schedule

**Decision**: Run both scripts in sequence in a single workflow: Sleeper sync first, news filter second. Schedule every 6 hours (4× per day).

**Rationale**: News filtering depends on a current roster list, so ordering matters. Committing cached JSON back to the repo via `git push` inside the workflow means the static site always reflects the latest data without a separate deploy step.

**Alternative considered**: Separate workflows with a `workflow_run` trigger. Adds complexity for no benefit at this scale; a single sequential workflow is easier to debug.

## Risks / Trade-offs

- **Sleeper API has no published SLA** → Mitigation: stale-cache fallback; worst case is stale data displayed on the site, not a broken build.
- **Committing cache files to the repo inflates git history** → Mitigation: keep cache files small (rosters + matchups fit comfortably under 100 KB). If history becomes a problem, switch to GitHub Actions artifacts in a future change.
- **RotoWire RSS structure could change** → Mitigation: `feedparser` is tolerant of feed variations; if the feed format changes dramatically, the script exits with a non-zero code and preserves the stale cache, alerting via Actions failure notification.
- **Name-substring matching may miss hyphenated or abbreviated names** → Accepted trade-off; the alternative (a fuzzy-match library) adds dependency weight and complexity disproportionate to the value at this stage.

## Migration Plan

1. Add `cache/.gitkeep` to the repo.
2. Add `scripts/sync_sleeper.py` and `scripts/sync_news.py`.
3. Update `requirements.txt` with pinned `requests` and `feedparser` versions.
4. Add `.github/workflows/sync.yml` with the schedule and sequential steps.
5. Manually trigger the workflow once and verify both cache files are written and committed.
6. Rollback: disable or delete the workflow file; revert `requirements.txt`. Cache files can be left in place or removed — they are read-only inputs for downstream features that don't exist yet.
