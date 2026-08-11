## 1. Data Files

- [x] 1.1 Create `data/league_rules_extra.json` with the schema defined in design.md: top-level `last_updated`, `last_updated_by`, and `rules` array of `{category, rule}` objects; seed with two example entries covering general league philosophy and keeper cost so owners have a working template to edit
- [x] 1.2 Create `data/league_rules_extra_schema.md`: document each field in `league_rules_extra.json` (`last_updated`, `last_updated_by`, `rules[].category`, `rules[].rule`) with types and examples, so owners know how to add entries

## 2. Sync Script

- [x] 2.1 Create `scripts/sync_league_settings.py`; load `config.yaml` for `league_id`; call `GET https://api.sleeper.app/v1/league/{league_id}` with a 10-second timeout; on any HTTP or network error print to stderr and exit non-zero; on success write the full response plus a top-level `last_updated` ISO 8601 UTC timestamp atomically to `cache/league_settings.json`
- [x] 2.2 Smoke-test: run `python scripts/sync_league_settings.py`; verify `cache/league_settings.json` exists, contains `scoring_settings`, `settings`, and `last_updated`; inspect the `settings` dict for `max_keepers` and other keeper-related fields to understand what our league exposes

## 3. Page Generator

- [x] 3.1 Create `scripts/generate_rules_page.py`; define a `SCORING_LABEL` dict mapping common Sleeper scoring keys to human-readable labels (e.g., `"rec"` -> `"Reception"`, `"rush_yd"` -> `"Rushing yard"`, `"pass_yd"` -> `"Passing yard"`, `"pass_td"` -> `"Passing TD"`, `"rec_td"` -> `"Receiving TD"`, `"fum_lost"` -> `"Fumble lost"`; include at least 12 common keys); unknown keys fall back to the raw key name
- [x] 3.2 Implement the auto-synced section: load `cache/league_settings.json`; if missing, render placeholder; otherwise extract and render: roster size, total starters, starter slot breakdown (QB/RB/WR/TE/FLEX/SF), scoring type label, trade deadline (convert to readable date if set; "None" if 0 or absent), waiver type; render `_Auto-synced from Sleeper | Last synced: <timestamp>_` as the section footer
- [x] 3.3 Implement keeper detection: if `settings.max_keepers` is present and greater than 0, render a "Keeper Rules" subsection with `max_keepers` and any other keeper-related `settings` keys (e.g., `keeper_deadline`, `keeper_cost`); if absent or 0, omit the subsection entirely
- [x] 3.4 Implement the top scoring settings block: iterate `scoring_settings`; show only non-zero values; apply `SCORING_LABEL` for display; render as a plain two-column list (Label: value)
- [x] 3.5 Implement the manual section: load `data/league_rules_extra.json`; if missing, render "No group agreements on file"; otherwise group rules by `category` and render each group as a labeled list; append `_Manually maintained -- edit data/league_rules_extra.json to update | Last updated by: <author> on <date>_`
- [x] 3.6 Assemble `site/rules.md`: H1 title, auto-synced section with source label, Markdown horizontal rule divider, manual section with source label; write atomically via tempfile + os.replace
- [x] 3.7 Smoke-test: run `python scripts/generate_rules_page.py`; inspect `site/rules.md`; verify both sections appear with their source labels, the keeper subsection is present or absent as the league data dictates, and the scoring values are human-readable

## 4. GitHub Actions

- [x] 4.1 In `.github/workflows/sync.yml`, add a "Sync league settings" step (`python scripts/sync_league_settings.py`) after the Sleeper sync step; add a "Generate rules page" step (`python scripts/generate_rules_page.py`) after it; add `cache/league_settings.json` and `site/rules.md` to the `git add` line in the commit step
- [x] 4.2 Confirm no new Python packages are needed (both scripts use only `json`, `os`, `sys`, `tempfile`, `datetime`, `requests`, and `yaml` — all already in `requirements.txt`); no lockfile change needed
