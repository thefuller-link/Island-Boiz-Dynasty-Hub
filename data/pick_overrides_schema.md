# pick_overrides.json schema

Each entry in `pick_overrides.json` corrects or supplements Sleeper-derived pick ownership.
Add an entry when a pick's ownership can't be cleanly determined from Sleeper data
(e.g., conditional picks, manual corrections after a Sleeper glitch).

```json
[
  {
    "year": "2027",
    "round": 1,
    "original_owner": "MoooSo",
    "current_owner": "jetercole",
    "note": "Conditional: transfers if MoooSo finishes top 4 in 2026",
    "uncertain": true
  }
]
```

## Fields

| Field | Type | Description |
| --- | --- | --- |
| `year` | string | Draft year, e.g. `"2027"` |
| `round` | int | Round number 1-4 |
| `original_owner` | string | Sleeper display name of the team that originally owned this pick |
| `current_owner` | string | Sleeper display name of the team that currently holds this pick |
| `note` | string | Human-readable explanation (shown on the picks page) |
| `uncertain` | bool | `true` to flag this pick with `[?]` on the page |
