"""Interactive CLI for logging dynasty decisions and recording owner responses."""

import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone

import yaml

REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
CONFIG_FILE = os.path.join(REPO_ROOT, "config.yaml")
DECISIONS_FILE = os.path.join(REPO_ROOT, "data", "decisions.json")
SLEEPER_CACHE = os.path.join(REPO_ROOT, "cache", "sleeper.json")

VALID_TYPES = ["trade", "waiver-claim", "roster-move", "lineup", "other"]
VALID_RESPONSES = ["approve", "veto", "abstain"]


def load_config():
    if not os.path.exists(CONFIG_FILE):
        print(f"Error: config.yaml not found at {CONFIG_FILE}.", file=sys.stderr)
        sys.exit(1)
    with open(CONFIG_FILE, encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}
    owners = config.get("owners")
    if not owners:
        print("Error: 'owners' key missing from config.yaml.", file=sys.stderr)
        sys.exit(1)
    return [str(o) for o in owners]


def load_decisions():
    if not os.path.exists(DECISIONS_FILE):
        return []
    with open(DECISIONS_FILE, encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError as exc:
            print(
                f"Error: {DECISIONS_FILE} is not valid JSON: {exc}\n"
                "To recover: git checkout data/decisions.json",
                file=sys.stderr,
            )
            sys.exit(1)


def save_decisions(entries):
    os.makedirs(os.path.dirname(DECISIONS_FILE), exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(DECISIONS_FILE), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(entries, f, indent=2)
            f.write("\n")
        os.replace(tmp_path, DECISIONS_FILE)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


def prompt_owner(owners, label="Who are you?"):
    print(f"\n{label}")
    for i, name in enumerate(owners, 1):
        print(f"  {i}. {name}")
    lower_owners = [o.lower() for o in owners]
    while True:
        raw = input("Enter number or name: ").strip()
        try:
            idx = int(raw) - 1
            if 0 <= idx < len(owners):
                return owners[idx]
        except ValueError:
            pass
        if raw.lower() in lower_owners:
            return owners[lower_owners.index(raw.lower())]
        print(f"  Invalid. Enter a number 1–{len(owners)} or an exact name.")


def _suggest_lineup_deadline():
    """
    Return a suggested deadline string for lineup entries.
    Reads nfl_state from sleeper cache; if season_type == "regular", returns
    the upcoming Sunday at 16:00 UTC (2 hours before 1pm ET Sunday kickoff).
    Returns None if cache is unavailable or not in regular season.
    """
    if not os.path.exists(SLEEPER_CACHE):
        return None
    try:
        with open(SLEEPER_CACHE, encoding="utf-8") as f:
            sleeper = json.load(f)
        nfl_state = sleeper.get("nfl_state") or {}
        if nfl_state.get("season_type") != "regular":
            return None
        now = datetime.now(timezone.utc)
        # Weekday: Monday=0, Sunday=6
        days_until_sunday = (6 - now.weekday()) % 7
        if days_until_sunday == 0 and now.hour >= 16:
            days_until_sunday = 7  # This Sunday's window has passed, suggest next
        target = now + timedelta(days=days_until_sunday)
        deadline = datetime(target.year, target.month, target.day, 16, 0, 0, tzinfo=timezone.utc)
        return deadline.strftime("%Y-%m-%d 16:00 UTC")
    except Exception:
        return None


def prompt_constrained(label, options):
    print(f"\n{label}: {', '.join(options)}")
    lower_opts = [o.lower() for o in options]
    while True:
        raw = input("> ").strip()
        if raw.lower() in lower_opts:
            return options[lower_opts.index(raw.lower())]
        print(f"  Invalid. Choose from: {', '.join(options)}")


def new_entry_flow(owners):
    print("\n--- New Decision ---")

    proposer = prompt_owner(owners)
    entry_type = prompt_constrained("Type", VALID_TYPES)

    print("\nDescription (required):")
    while True:
        description = input("> ").strip()
        if description:
            break
        print("  Description cannot be empty.")

    my_response = prompt_constrained("Your response", VALID_RESPONSES)

    # Lineup-specific fields
    deadline = None
    proposed_lineup = None
    if entry_type == "lineup":
        suggestion = _suggest_lineup_deadline()
        if suggestion:
            print(f"\nDeadline (suggested: {suggestion})")
            print("Press Enter to accept, or type your own (YYYY-MM-DD HH:MM UTC):")
        else:
            print("\nDeadline (YYYY-MM-DD HH:MM UTC, e.g. 2026-09-06 16:00 UTC):")
        while True:
            raw = input("> ").strip()
            if not raw and suggestion:
                raw = suggestion
            try:
                dt = datetime.strptime(raw.replace(" UTC", ""), "%Y-%m-%d %H:%M")
                deadline = dt.replace(tzinfo=timezone.utc).isoformat()
                break
            except ValueError:
                print("  Invalid format. Use YYYY-MM-DD HH:MM UTC (e.g. 2026-09-06 16:00 UTC).")

        print("\nProposed starters (comma-separated player names or Sleeper IDs):")
        while True:
            raw = input("> ").strip()
            parts = [p.strip() for p in raw.split(",") if p.strip()]
            if parts:
                proposed_lineup = parts
                break
            print("  Enter at least one player name or ID.")

    print("\nRationale (optional — press Enter to skip):")
    rationale = input("> ").strip()

    responses = {owner: "pending" for owner in owners}
    responses[proposer] = my_response

    now = datetime.now(timezone.utc)
    entry_id = now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"
    entry = {
        "id": entry_id,
        "date": now.strftime("%Y-%m-%d"),
        "type": entry_type,
        "proposer": proposer,
        "description": description,
        "responses": responses,
    }
    if deadline is not None:
        entry["deadline"] = deadline
    if proposed_lineup is not None:
        entry["proposed_lineup"] = proposed_lineup
    if rationale:
        entry["rationale"] = rationale

    entries = load_decisions()
    entries.append(entry)
    save_decisions(entries)
    print(f"\nOK: Decision logged. ID: {entry_id}")


def respond_flow(owners):
    print("\n--- Record Response ---")

    owner = prompt_owner(owners)
    entries = load_decisions()
    pending = [e for e in entries if e.get("responses", {}).get(owner) == "pending"]

    if not pending:
        print(f"\nNo decisions are currently awaiting your response, {owner}.")
        return

    print(f"\nDecisions awaiting your response ({len(pending)}):")
    for i, e in enumerate(pending, 1):
        desc = e.get("description", "")
        if len(desc) > 60:
            desc = desc[:57] + "…"
        print(f"  {i}. [{e['date']}] {e['type']}")
        print(f"     {desc}")
        print(f"     id: {e['id'][:24]}…")

    while True:
        raw = input("\nSelect entry number: ").strip()
        try:
            idx = int(raw) - 1
            if 0 <= idx < len(pending):
                selected = pending[idx]
                break
        except ValueError:
            pass
        print(f"  Enter a number 1–{len(pending)}.")

    response = prompt_constrained("Your response", VALID_RESPONSES)

    for entry in entries:
        if entry["id"] == selected["id"]:
            entry["responses"][owner] = response
            break

    save_decisions(entries)
    print(f"\nOK: Response '{response}' recorded for entry {selected['id']}")


def main():
    owners = load_config()

    print("\nIslandBoiiiiiz Decision Log")
    print("  1. Log new decision")
    print("  2. Record my response to an existing entry")

    while True:
        mode = input("\nSelect mode (1 or 2): ").strip()
        if mode == "1":
            new_entry_flow(owners)
            break
        elif mode == "2":
            respond_flow(owners)
            break
        else:
            print("  Enter 1 or 2.")


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\nCancelled.")
        sys.exit(0)
