## Context

The existing `data/decisions.json` already stores per-owner responses (`approve` / `veto` / `abstain` / `pending`). This change adds a resolution layer on top without replacing that data or the scripts that write it. The only new script is `resolve_decisions.py`; the two existing scripts (`log_decision.py`, `generate_decision_summary.py`) are extended in place.

Current data flow:
```
log_decision.py --> data/decisions.json --> generate_decision_summary.py --> site/decisions.md
```

New data flow:
```
log_decision.py --> data/decisions.json --> resolve_decisions.py --> data/decisions.json
                                                                         |
                                                             generate_decision_summary.py --> site/decisions.md
```

The `resolve_decisions.py` step runs in `publish.yml` before `generate_decision_summary.py`, so every push to decisions.json triggers automatic resolution. It also runs as a standalone script any owner can call locally before reviewing the summary.

## Goals / Non-Goals

**Goals:**
- Compute resolution without requiring a separate group text
- Surface pending decisions prominently so stalls are impossible to miss
- Auto-resolve lineup entries at deadline; flag the outcome distinctly
- Keep the single-script interaction model — no new tool to learn

**Non-goals:**
- Push notifications (Slack, SMS, email)
- Time-based auto-resolution for transaction decisions
- Quorum beyond the current 3-owner group

## Decisions

### Resolution is written back to decisions.json, not computed at render time

**Decision:** `resolve_decisions.py` mutates decisions.json by adding `resolution` and `resolution_reason` fields. The page generator reads these fields rather than re-deriving resolution from responses on every render.

**Rationale:** Storing resolution makes it immutable once set — an already-resolved entry won't silently re-resolve if the KTC cache changes later. It also keeps the generator simple (no cache reads, no business logic). The downside is that resolutions must be "unlocked" by running resolve before render; publish.yml wires them in sequence so this is transparent.

**Alternative considered:** Compute resolution in the generator at render time — rejected because it makes the generator dependent on KTC/Sleeper caches and re-derives outcomes that should be stable.

### Resolved entries are immutable

**Decision:** `resolve_decisions.py` skips entries that already have a non-pending `resolution`. Once written, a resolution cannot be overwritten by a subsequent run.

**Rationale:** Prevents a scenario where a late cache update (e.g., a player's KTC value drops and they fall out of top-3) silently changes a previously approved decision from majority to unanimous required, retroactively invalidating it. If a resolution was wrong, it must be corrected manually.

**Alternative considered:** Re-derive resolution on every run — rejected for the reason above.

### Top-3 player check: normalize names, match against KTC player list cross-referenced with roster

**Decision:** At resolution time, `resolve_decisions.py` loads `cache/sleeper.json` to get roster_id=2's player IDs, then loads `cache/ktc.json` to get those players' values, ranks them, and takes the top 3. It then checks whether any normalized name from the top-3 list appears as a substring of the normalized decision description.

Name normalization is the same function used in `analyze_trade.py` and `sync_ktc.py`: lowercase, strip punctuation, collapse spaces. Substring match is used rather than exact match because descriptions are free text (e.g., "trade Ja'Marr Chase" contains "jamarr chase").

**Rationale:** Consistent with existing name-matching conventions in the codebase. Substring match is loose but acceptable — a false positive means the system applies unanimous rule unnecessarily (safe direction); a false negative would miss a required unanimous vote (unsafe). Substring errs on the safe side.

**Alternative considered:** Exact-match only — too brittle for free-text descriptions. Token-based fuzzy match — over-engineered for 3 names.

### 1st-round pick detection: text pattern, not structured assets field

**Decision:** Detect future 1st-round picks by searching the normalized description for ("1st") AND at least one of ("2026", "2027", "2028", "pick"). This is a deliberate heuristic, not a structured field parse.

**Rationale:** Decision descriptions are already entered as free text and there is no structured `assets` field in the schema. Adding one would break the lightweight input model. The heuristic catches the common cases ("send 2027 1st", "trade a 2026 1st-rounder") and false positives apply unanimous rule, which is safe.

**Alternative considered:** Add a structured `assets` field to the entry schema — deferred; would require changes to log_decision.py's input flow and backward compatibility handling for all existing entries.

### Lineup deadline: auto-suggest from nfl_state, manual override

**Decision:** When logging a lineup entry, `log_decision.py` reads `cache/sleeper.json` `nfl_state` for the current week's game lock time. If the field is present, it suggests (deadline = game_lock - 2 hours). If absent or not in regular season, it prompts the user to enter a deadline manually. Deadline is stored as an ISO 8601 UTC string.

**Rationale:** The Sleeper `nfl_state` object includes season_type and week but not always a precise per-game lock time. The 2-hour buffer is a pragmatic safe default for the Sunday 1pm ET window; owners can override for Thursday Night or Monday Night games. Storing the deadline as UTC avoids timezone ambiguity on render.

### publish.yml: resolve step runs before generate step

**Decision:** Add `python scripts/resolve_decisions.py` as a step in `publish.yml` between `actions/checkout` and `generate_decision_summary.py`. The workflow already triggers on pushes to `data/decisions.json`.

**Rationale:** This keeps resolution invisible to owners — they push a response, the workflow resolves and generates in one commit. The `[skip ci]` commit from the generate step already prevents loops.

## Risks / Trade-offs

- **KTC cache stale at resolution time:** If `cache/ktc.json` is stale and a player has dropped from top-3 since the cache was last written, the resolution may use an outdated top-3 list. Mitigated by immutability (once resolved, it stays resolved) and by the safe-fallback direction of substring matching.
- **Free-text false positives:** "1st down" in a description would trigger the 1st-round pick pattern. Mitigated by requiring both "1st" and at least one of "2026"/"2027"/"2028"/"pick". "1st down 2027" is an unlikely description.
- **Lineup deadline without nfl_state game lock:** Sleeper's `nfl_state` exposes week but not always a per-game lock timestamp. The 2-hour buffer from the suggestion is a proxy, not a precise lock. Owners should double-check Thursday and Monday night game deadlines manually.
