## Context

Two new single-purpose scripts join the existing cache pipeline. `sync_ktc.py` fetches dynasty values from KeepTradeCut and writes `cache/ktc.json`; `analyze_trade.py` reads `cache/ktc.json` and `cache/sleeper.json` (already produced by roster-news-sync), prompts the user for a trade, and prints a verdict. Both scripts follow the same conventions already established for `sync_sleeper.py` and `sync_news.py`.

**KTC data access:** KeepTradeCut does not publish a documented API. Their values are exposed at a public JSON endpoint (`https://keeptradecut.com/dynasty-rankings?format=2` or the underlying `ktc-user-data.js` file served on their rankings page) that the community uses without authentication. The URL is undocumented and may change — the sync script should handle HTTP errors gracefully and fall back to stale cache.

Data flow:

```
KTC endpoint → sync_ktc.py → cache/ktc.json
Sleeper API → sync_sleeper.py → cache/sleeper.json (existing)
                                      ↓
                            analyze_trade.py (interactive)
                                      ↓
                              verdict to stdout
                              [optional] data/decisions.json
```

## Goals / Non-Goals

**Goals:**
- Fetch and cache KTC dynasty player + pick values on the same schedule as Sleeper sync
- Provide an interactive CLI that accepts a trade, looks up values, applies adjustments, and prints a structured verdict
- Add `team_mode` per owner to `config.yaml`

**Non-Goals:**
- Backend server or database (out-of-scope per project architecture)
- Web-based trade UI or real-time fetch at evaluation time
- LLM-generated narrative (deferred to a future change)
- Historical value tracking or charting

## Decisions

### KTC over DynastyProcess

**Decision:** Use KeepTradeCut values rather than DynastyProcess/FantasyPros data.

**Rationale:** KTC is crowdsourced and updated daily; its data includes exact pick values (e.g., "2026 Early 1st") which DynastyProcess does not publish in a scriptable format. KTC values are the de-facto community standard for dynasty trades; most owners already reference them. DynastyProcess requires scraping HTML or pulling from a GitHub-hosted CSV that covers only a subset of assets.

**Alternative considered:** FantasyPros/DynastyProcess open files — rejected because pick coverage is incomplete and the format changes frequently.

### Name matching via normalized key

**Decision:** Store a `name_key` (lowercase, no punctuation, single spaces) on each KTC player entry. During trade input, normalize the user's typed name the same way before lookup.

**Rationale:** Player names vary in punctuation and spacing ("D'Andre Swift" vs "Dandre Swift"). Exact string matching fails too often in a CLI input scenario. A normalized key covers the common cases without requiring a full fuzzy-match library.

**Alternative considered:** `difflib.get_close_matches` — would add false positives and complicate the "unknown player" flow; deferred as an enhancement.

### Pick-weight multipliers as fixed constants

**Decision:** Define rebuild/retool/contend multipliers as named constants (e.g., `REBUILD_WEIGHT = 1.20`, `RETOOL_WEIGHT = 1.05`, `CONTEND_WEIGHT = 0.85`) in the script rather than in config.yaml.

**Rationale:** These weights are subjective and will need calibration. Putting them in code makes changes visible in git diffs and ties them to the script version. If owners want to tune them, they can edit the script — that's a deliberate friction point that prevents casual drift.

**Alternative considered:** Expose as config.yaml keys — deferred until we've used the defaults long enough to know what values are right.

### Redundancy threshold: two existing starters = flag

**Decision:** Flag positional redundancy when the receiving team already has ≥2 rostered players at the same position being acquired. Use Sleeper player metadata's `position` field.

**Rationale:** Dynasty rosters carry 30+ players; it's normal to have depth. The threshold of 2+ starters at a position before flagging avoids noisy false positives while catching actual roster pile-ups. "Starter-tier" is approximated by presence on a 30-man dynasty roster (not practice squad).

**Alternative considered:** Tier-based threshold using KTC value rank to distinguish starter vs. depth — adds complexity without meaningful gain at this scale.

### Decision-log integration via direct JSON write

**Decision:** When the user opts in, `analyze_trade.py` writes directly to `data/decisions.json` using the same atomic write pattern as `log_decision.py`, rather than calling `log_decision.py` as a subprocess.

**Rationale:** Subprocess invocation adds fragile path resolution and makes the control flow harder to follow. Both scripts share the same JSON schema — duplicating the write logic is minimal.

## Risks / Trade-offs

- **KTC endpoint instability** → Mitigation: stale-cache fallback already required by spec; sync step fails loudly so the GitHub Actions log surfaces it quickly
- **Name matching failures** → Mitigation: unknown-player prompt lets the user correct the input; verdict is never silently wrong. Full fuzzy match is a deferred enhancement.
- **Pick label format mismatch** (user types "26 1st" vs KTC stores "2026 Early 1st") → Mitigation: display the full list of pick labels and let the user select by number if the typed label doesn't match
- **Pick-weight multipliers feel arbitrary** → Mitigation: constants are code-visible, documented here, and easy to adjust via a one-line PR

## Open Questions

- Is KTC's exact public endpoint URL stable enough to hardcode, or should it be in config.yaml so it can be updated without a code change? (No decision needed before implementation — start with a constant; move to config if it breaks once.)
