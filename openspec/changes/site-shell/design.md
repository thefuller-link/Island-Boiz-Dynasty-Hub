## Context

See proposal.md (Why) for motivation. The eight applied features each produce JSON caches and/or markdown files; none produce HTML. GitHub Pages will serve the `site/` directory. The three generator scripts become the only place where HTML is assembled — feature scripts stay single-purpose.

Existing output files relevant to each page:
- Today: `cache/news.json`, `data/decisions.json`
- Rookies & Picks: `cache/picks.json`, `cache/prospects.json`, `cache/consensus.json`, `cache/usage.json`
- Reference: `cache/league_settings.json`, `data/league_rules_extra.json`

`generate_rules_page.py` currently writes `site/rules.md`. The reference generator replaces that output with HTML; `site/rules.md` generation can be kept in place for backward compatibility or removed once HTML is confirmed working.

## Goals / Non-Goals

**Goals:**
- Produce three browsable HTML pages from existing cache files without modifying feature scripts
- Apply a consistent dark-mode design system across all pages via a single shared stylesheet
- Keep the build purely Python + stdlib (no JS bundler, no Jinja2 install, no new pip packages)
- Degrade gracefully per section so a missing cache never blanks a page

**Non-Goals:**
- Interactive features, client-side routing, or localStorage tab memory
- Light/dark toggle or any theme other than dark
- Changes to any existing feature sync script or its cache format
- New Python dependencies

## Decisions

### Decision: Plain Python string generation, not Jinja2
The instructions say generators use "only stdlib + yaml + json." Jinja2 is not in requirements.txt and adding it conflicts with the no-new-dependencies requirement. Plain Python f-strings and list-join produce readable, maintainable HTML at this scale (three pages, single column layouts with a handful of sections each).

_Alternative considered:_ Jinja2 templates — cleaner separation of logic and markup, but requires a new dependency and a template directory to maintain. Rejected to satisfy the lockfile constraint.

### Decision: Three separate HTML files, not a single-page app
Static pages with real URL links are simpler to deploy on GitHub Pages (no hash routing needed), work without JavaScript, and are linkable by page. The bottom-tab nav links are standard `<a href>` tags; the active tab is set at generation time by embedding the `active` class in the rendered HTML, not at runtime.

_Alternative considered:_ Single index.html with JS-driven tab panels — eliminates three-file coordination overhead, but requires JavaScript to be correct and breaks direct linking. Rejected.

### Decision: Stylesheet embedded via `<link>` to `static/style.css`
All three pages reference `static/style.css` with a relative path. CSS custom properties (variables) handle the color system so the accent color and surface colors are defined once at `:root`.

_Alternative considered:_ Inline `<style>` per page — no external file to manage, but the stylesheet is duplicated across three files and any design tweak requires editing three places. Rejected.

### Decision: Stale threshold is 24 hours, section-level
Each generator reads the `last_updated` or `published` timestamp embedded in each cache file and compares to the current UTC time at render time. If the delta exceeds 24 hours the section prepends a warning but still renders the stale content. If the cache file is absent the section renders a "not yet synced" notice. No whole-page errors.

### Decision: `generate_reference_page.py` replaces `generate_rules_page.py` output target
`generate_rules_page.py` writes `site/rules.md`. The new reference generator writes `site/reference.html`. Both can coexist; `sync.yml` runs both. `site/rules.md` is harmless to keep until the HTML page is confirmed working on GitHub Pages.

## Data Flow

```
Sleeper API --> sync_sleeper.py --> cache/sleeper.json
RotoWire RSS --> sync_news.py --> cache/news.json
KTC HTML --> sync_ktc.py --> cache/ktc.json
                          --> sync_picks.py --> cache/picks.json
nflverse --> sync_usage.py --> cache/usage.json
CFBD API --> sync_prospects.py --> cache/prospects.json + cache/consensus.json
Sleeper API --> sync_league_settings.py --> cache/league_settings.json
data/decisions.json (written by log_decision.py / resolve_decisions.py)
data/league_rules_extra.json (manually maintained)

cache/news.json + data/decisions.json --> generate_today_page.py --> site/index.html
cache/picks.json + cache/prospects.json + cache/consensus.json + cache/usage.json
    --> generate_rookies_page.py --> site/rookies.html
cache/league_settings.json + data/league_rules_extra.json
    --> generate_reference_page.py --> site/reference.html

site/index.html + site/rookies.html + site/reference.html + site/static/style.css
    --> GitHub Pages --> owner browser
```

## Risks / Trade-offs

[Risk: Active tab class set at render time] → If an owner bookmarks a deep URL and then the file is regenerated, the active tab is still correct because the class is baked into each file for its own page. No risk.

[Risk: Relative path to `static/style.css` breaks if pages are served from a subdirectory] → GitHub Pages serves from the repo root of `site/`, so `static/style.css` resolves correctly. If the Pages root is ever changed, paths break silently. Mitigation: add a brief note in the README about the required Pages config.

[Risk: Stale 24-hour threshold is arbitrary] → Sync runs every 6 hours; 24 hours covers up to 4 missed syncs. Acceptable for a fantasy football hub where minute-level freshness is not required.

[Risk: `publish.yml` commits HTML; `sync.yml` also commits HTML] → Both workflows run `git push`. If they race on the same branch, one push will fail. Mitigation: both use `git diff --staged --quiet || git commit` so a no-op build never pushes, reducing race probability. True fix would be a single workflow or branch protection; deferred as out of scope.

## Migration Plan

1. Create `site/static/style.css` and `site/.nojekyll`
2. Create three generator scripts; smoke-test each locally against existing cache files
3. Update `sync.yml` to run generators after data syncs; update `publish.yml` to run `generate_today_page.py`
4. One-time: configure GitHub Pages to serve from `site/` directory (manual repo setting)
5. Push and verify pages load at the Pages URL

Rollback: remove the three HTML files and revert workflow changes. `site/rules.md` is unaffected and remains the fallback Reference output.
