## Why

All eight applied features produce data and markdown output but there is no unified entry point — no shared navigation, no consistent visual design, and no actual HTML served to GitHub Pages. Owners currently have no single URL to open on their phone. This change wires everything together into a real, usable site.

## What Changes

- New `site/static/style.css`: shared dark-mode CSS design system (colors, typography, spacing, nav component, responsive layout)
- New `scripts/generate_today_page.py`: reads `cache/news.json` + `data/decisions.json` → `site/index.html`; sections: News, Decisions & Votes (chronological, most recent first)
- New `scripts/generate_rookies_page.py`: reads `cache/picks.json`, `cache/prospects.json`, `cache/consensus.json`, `cache/usage.json` → `site/rookies.html`; sections: Rising Free Agents, Pick Tracker, Prospect Board
- New `scripts/generate_reference_page.py`: reads `cache/league_settings.json` + `data/league_rules_extra.json` → `site/reference.html`; replaces `site/rules.md` as the authoritative rendered output
- New `site/.nojekyll`: disables Jekyll processing so `site/static/` is served as-is
- Updated `sync.yml`: adds HTML generation steps after each data sync; commits HTML files alongside existing cache files
- Updated `publish.yml`: adds `generate_today_page.py` step so decision/vote pushes also regenerate Today

## Capabilities

### New Capabilities

- `site-shell`: Three-page HTML site with shared dark-mode design, bottom tab bar nav on mobile (top nav on desktop), defensive per-section stale/missing data handling, and no JS framework dependency

### Modified Capabilities

_(none — existing feature scripts are unchanged; site-shell adds a new HTML rendering layer only)_

## Impact

- **New files**: `site/static/style.css`, `site/index.html`, `site/rookies.html`, `site/reference.html`, `site/.nojekyll`, three new generator scripts
- **Modified workflows**: `sync.yml` (add HTML generation steps + git add), `publish.yml` (add `generate_today_page.py` step)
- **No changes** to existing feature sync or page-generator scripts
- **No new dependencies**: generators use only stdlib + `yaml` + `json` (already in requirements.txt)
- Relates to priority feature: **none** (presentation layer tying all features together)
- GitHub Pages must be configured to serve from the `site/` folder (one-time repo setting, not automated)

## Non-goals

- No live/interactive trade calculator — the decisions log surfaces trade votes statically; analyze_trade.py remains CLI-only
- No JavaScript framework, build pipeline, or bundler
- No per-user sessions, authentication, or personalization
- No light/dark mode toggle — dark is the only mode
- No memory of last-viewed tab (Today always loads on open)
- No changes to any existing feature script or its output format
