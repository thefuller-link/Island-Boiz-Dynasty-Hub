## Why

Owners frequently need to look up league rules mid-season (roster limits, scoring, keeper eligibility) and currently have no canonical place to do so — the Sleeper app buries settings several taps deep. This page surfaces the rules automatically from Sleeper's own data, so it never goes stale and requires no manual transcription.

## What Changes

- New `scripts/sync_league_settings.py`: calls `GET /league/{league_id}` and caches the response to `cache/league_settings.json`; runs as part of the existing roster-news sync cadence
- New `data/league_rules_extra.json`: manually-maintained file for rules not expressible in Sleeper settings (group agreements, informal side rules); included in the repo with a starter template
- New `scripts/generate_rules_page.py`: reads both sources and writes `site/rules.md` with two clearly labeled sections — "League Settings (auto-synced from Sleeper)" and "Group Agreements (manually maintained)"
- Updated `.github/workflows/sync.yml`: adds `sync_league_settings.py` and `generate_rules_page.py` steps and commits `cache/league_settings.json site/rules.md`

## Capabilities

### New Capabilities

- `keeper-rules-cheatsheet`: Auto-synced league settings page combining Sleeper API data (roster limits, scoring, keeper config if any) with a manually-maintained supplementary section for informal group agreements; clearly labels which section is auto-pulled vs. hand-edited; shows last-synced timestamp and last-updated-by attribution

### Modified Capabilities

_(none)_

## Impact

- **API**: One additional call to `GET /league/{league_id}` per sync run — Sleeper public API, no key required, negligible quota impact
- **New cache file**: `cache/league_settings.json`
- **New data file**: `data/league_rules_extra.json` (committed, manually edited by owners)
- **New site page**: `site/rules.md`
- **Modified workflow**: `.github/workflows/sync.yml` gains two steps and two files in the git add line
- Relates to priority feature: **none** (supporting utility, standalone)

## Non-goals

- No edit UI — owners update `data/league_rules_extra.json` directly via git
- No scoring calculator or rule simulation
- No diff/change history beyond what git provides
- No alerting when Sleeper settings change
