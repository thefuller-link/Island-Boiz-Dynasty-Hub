## Context

See `proposal.md` — Why. Current state: no decision history exists anywhere. The project has no backend and no database; all persistence must live in committed files.

Data flow for this change:

```
Owner runs log_decision.py
        │
        ▼ (prompts: type, description, response, rationale)
data/decisions.json  ◄──── append-only source of truth (committed to repo)
        │
        ▼ (generate_decision_summary.py — runs on push via GitHub Actions)
site/decisions.md  ──► GitHub Pages static site
```

Owner names and configuration live in the existing `config.yaml`. No network calls. No new dependencies beyond Python stdlib.

## Goals / Non-Goals

**Goals:**
- A durable, human-readable source of truth that survives indefinitely via git history.
- A zero-friction entry point: an owner should be able to log a decision in under a minute without knowing JSON.
- A rendered view that surfaces pending items without anyone having to grep the JSON.

**Non-Goals:**
- Real-time collaboration or conflict resolution — two owners running `log_decision.py` simultaneously would cause a git merge conflict; this is accepted and handled through the same git workflow the rest of the repo uses.
- Authentication or access control.
- Editing or deleting past entries (see `decision-entry` spec).

## Decisions

### `data/decisions.json` as a JSON array, not newline-delimited JSON

**Decision**: The log is a standard JSON array (`[ {...}, {...} ]`), not NDJSON (one JSON object per line).

**Rationale**: Standard JSON is readable without tooling, trivially parseable with `json.load()`, and works naturally as a committed file. The downside is that appending requires reading the full file, removing the trailing `]`, appending the new entry, and re-writing `]` — a minor implementation concern, not a behavioral one. At the scale of a dynasty league (tens to low hundreds of entries per season), the file stays well under 1 MB.

**Alternative considered**: NDJSON (append a line). Cheaper I/O for appends, but requires a custom parser or a dependency, and the file isn't readable as-is without tooling.

### Owner names live in `config.yaml`, not hardcoded

**Decision**: The list of valid owner names is read from `config.yaml` (`owners` key) at runtime by both scripts.

**Rationale**: `config.yaml` is already established as the configuration file for this project (the roster-news-sync change uses it for the watchlist). Centralizing owner identity there means a future owner change requires editing one file, not hunting through scripts.

**Alternative considered**: Hardcode the three names as constants in each script. Simpler, but brittle if an owner display name ever changes, and inconsistent with the config.yaml pattern.

### Atomic write via read-modify-write with a temp file

**Decision**: `log_decision.py` reads the current array, appends the new entry in memory, writes to a temporary file in the same directory, then renames the temp file over `data/decisions.json`.

**Rationale**: A rename is atomic on the same filesystem, satisfying the spec's "no partial entry" requirement. Writing directly to the target file risks leaving a truncated file if the process is interrupted mid-write.

**Alternative considered**: Write directly to the file. Simpler, but violates the atomicity requirement in the `decision-input` spec.

### Summary generation on push, not on a schedule

**Decision**: `generate_decision_summary.py` is triggered by a GitHub Actions `push` event (on the branch that serves GitHub Pages), not the periodic sync schedule.

**Rationale**: Decisions are logged manually and infrequently (not every 6 hours). Re-generating the summary on every push means the site always reflects the latest committed `data/decisions.json` with no polling lag. The sync schedule workflow is for external data pulls; this is an internal render step.

**Alternative considered**: Add it to the existing sync schedule. Works, but introduces up to 6 hours of lag between a logged decision and it appearing on the site.

### Markdown output rendered as a plain Python string, not Jinja2

**Decision**: `generate_decision_summary.py` uses Python f-strings to build the Markdown output, not a Jinja2 template.

**Rationale**: The summary structure is straightforward (a header, a loop over entries, a pending section). A Jinja2 template would add a dependency and an indirection layer for no gain at this complexity level. If the output ever becomes complex enough to warrant templates, that's a future refactor.

## Risks / Trade-offs

- **Concurrent writes by two owners** → Mitigation: this is a git conflict, handled identically to any other concurrent edit. Both owners would see a merge conflict on `data/decisions.json` and resolve it manually (the JSON array format makes conflicts readable). Acceptable for a 3-person team.
- **`data/decisions.json` grows unboundedly over seasons** → Accepted trade-off; the file is plaintext JSON and will grow slowly (hundreds of entries per year at most). If size ever becomes a concern, a future change can add archival logic.
- **No validation of prior entries on append** → If the file is manually corrupted, `log_decision.py` will fail to load it and exit with an error. Mitigation: the error message directs the user to inspect the file. Recovery is via git (`git checkout data/decisions.json`).

## Migration Plan

1. Add `owners` key to `config.yaml` listing the three owner names.
2. Create `data/decisions.json` as an empty array `[]` (or `data/.gitkeep` with creation-on-first-use logic in the script).
3. Add `scripts/log_decision.py` and `scripts/generate_decision_summary.py`.
4. Add or update the GitHub Actions workflow to run `generate_decision_summary.py` on push.
5. One owner runs `log_decision.py` to log the first decision and verifies the output.
6. Rollback: remove the two scripts and the workflow step; `data/decisions.json` and `site/decisions.md` can be left or deleted — no downstream feature depends on them yet.
