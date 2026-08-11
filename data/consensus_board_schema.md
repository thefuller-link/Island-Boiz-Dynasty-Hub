# consensus_board.json schema

Each entry in `data/consensus_board.json` represents one prospect on the manually-maintained big board.
Update this file via PR whenever the consensus rankings shift materially.
`sync_consensus.py` reads this file and stages it to `cache/consensus.json` with a timestamp.

```json
[
  {
    "name": "Travis Hunter",
    "position": "WR",
    "school": "Colorado",
    "consensus_rank": 1,
    "source": "manual"
  }
]
```

## Fields

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `name` | string | yes | Player's full name as it appears in CFBD data |
| `position` | string | yes | Position abbreviation: WR, RB, TE, QB |
| `school` | string | yes | College/university name |
| `consensus_rank` | int | yes | Rank on the big board (1 = top prospect) |
| `source` | string | no | Where this rank came from, e.g. "manual", "dynastyprocess", "dynastynerds" |
