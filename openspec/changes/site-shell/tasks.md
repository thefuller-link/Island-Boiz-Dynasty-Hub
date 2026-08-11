## 1. Static Assets

- [x] 1.1 Create `site/.nojekyll` (empty file) to disable Jekyll processing on GitHub Pages
- [x] 1.2 Create `site/static/style.css`: define CSS custom properties at `:root` for surface colors (dark bg, card bg), text colors (primary, muted), one accent color, and spacing scale; implement base reset, body/container layout, nav component (bottom tab bar at <= 768px, top nav at > 768px), section card styles, stale/missing warning banner, and responsive single-column page layout

## 2. Shared HTML Helpers

- [x] 2.1 Create `scripts/html_utils.py`: implement `page_shell(title, active_tab, body_html)` → full HTML string with `<!DOCTYPE html>`, `<head>` (charset, viewport, title, stylesheet link to `../static/style.css`), nav component with three links (Today → `index.html`, Rookies & Picks → `rookies.html`, Reference → `reference.html`) with the active tab's link getting `class="active"`, and `<main>` wrapper around `body_html`; implement `stale_banner(label, timestamp_str, threshold_hours=24)` → warning HTML if timestamp is older than threshold or file was absent; implement `missing_section(label)` → placeholder HTML for absent cache

## 3. Today Page Generator

- [x] 3.1 Create `scripts/generate_today_page.py`: load `cache/news.json` and `data/decisions.json`; render a **News** section (entries sorted reverse chronological by published date, each showing headline + source + timestamp) with stale/missing handling; render a **Decisions & Votes** section (entries sorted reverse chronological by created_at, each showing description, resolution status label, and resolution_reason if resolved) with stale/missing handling; assemble via `html_utils.page_shell` with `active_tab="today"`; write atomically to `site/index.html`
- [x] 3.2 Smoke-test: run `python scripts/generate_today_page.py`; verify `site/index.html` exists, contains the nav with Today marked active, and both sections appear (or their placeholders if caches are absent)

## 4. Rookies & Picks Page Generator

- [x] 4.1 Create `scripts/generate_rookies_page.py`: load `cache/usage.json`, `cache/picks.json`, `cache/prospects.json`, `cache/consensus.json`; render **Rising Free Agents** section from usage data (same content as `site/usage.md` but as HTML table rows) with stale/missing handling; render **Pick Tracker** section from picks data (same content as `site/picks.md` formatted as HTML) with stale/missing handling; render **Prospect Board** section combining prospects and consensus data with stale/missing handling; assemble via `html_utils.page_shell` with `active_tab="rookies"`; write atomically to `site/rookies.html`
- [x] 4.2 Smoke-test: run `python scripts/generate_rookies_page.py`; verify `site/rookies.html` exists, Rookies & Picks tab is marked active in nav, and each section renders content or a placeholder

## 5. Reference Page Generator

- [x] 5.1 Create `scripts/generate_reference_page.py`: port the rendering logic from `generate_rules_page.py` to HTML output (reuse `_render_auto_section` and `_render_manual_section` logic but emit `<section>`, `<h2>`, `<ul>`, `<p>` tags instead of Markdown); load `cache/league_settings.json` and `data/league_rules_extra.json`; render auto-synced section with source label and last-synced timestamp footer; render manual section with source label and last-updated attribution; assemble via `html_utils.page_shell` with `active_tab="reference"`; write atomically to `site/reference.html`
- [x] 5.2 Smoke-test: run `python scripts/generate_reference_page.py`; verify `site/reference.html` exists, Reference tab is marked active, and both sections (or their placeholders) appear with their source labels

## 6. GitHub Actions Integration

- [x] 6.1 In `sync.yml`, add a "Generate today page" step (`python scripts/generate_today_page.py`) after the news sync step; add a "Generate rookies page" step (`python scripts/generate_rookies_page.py`) after the picks/usage generation steps; add a "Generate reference page" step (`python scripts/generate_reference_page.py`) after the existing "Generate rules page" step; add `site/index.html site/rookies.html site/reference.html` to the `git add` line in the commit step
- [x] 6.2 In `publish.yml`, add a "Generate today page" step (`python scripts/generate_today_page.py`) before the "Commit updated summary" step; add `site/index.html` to the `git add` line in that commit step
- [x] 6.3 Verify no new packages were added to `requirements.txt` (all three generators use only stdlib + `yaml` + `json`)
