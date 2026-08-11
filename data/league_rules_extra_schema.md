# league_rules_extra.json Schema

This file holds informal group agreements that are not encoded as Sleeper platform settings. It is committed to the repo and manually edited by owners. Changes take effect on the next sync run.

## Top-level fields

| Field | Type | Description |
|-------|------|-------------|
| `last_updated` | string (YYYY-MM-DD) | Date the file was last edited. Used in the rules page attribution line. |
| `last_updated_by` | string | Owner name who made the last edit (e.g., "LWFuller"). Shown in the "manually maintained" footer. |
| `rules` | array | List of rule objects. See below. |

## Rule object fields

| Field | Type | Description |
|-------|------|-------------|
| `category` | string | Grouping label shown as a subheading on the rules page. Examples: "General", "Keeper", "Trades", "Waivers". |
| `rule` | string | The rule text, written as a complete sentence. Displayed as a list item under its category. |

## Example

```json
{
  "last_updated": "2026-08-07",
  "last_updated_by": "LWFuller",
  "rules": [
    {
      "category": "General",
      "rule": "No tanking or rebuild-tanking for draft picks."
    },
    {
      "category": "Keeper",
      "rule": "Keeper cost is the round directly above where the player was originally drafted."
    }
  ]
}
```

## How to update

1. Edit `data/league_rules_extra.json` in any text editor or GitHub's web editor.
2. Update `last_updated` to today's date and `last_updated_by` to your owner name.
3. Commit the change to `main`. The rules page will regenerate on the next sync run.
