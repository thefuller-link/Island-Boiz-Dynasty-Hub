"""Stage data/consensus_board.json into cache/consensus.json."""

import json
import os
import sys
import tempfile
from datetime import datetime, timezone

SOURCE_FILE = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "data", "consensus_board.json"))
CACHE_FILE = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "cache", "consensus.json"))


def main():
    if not os.path.exists(SOURCE_FILE):
        print(
            "Error: No consensus board found - create data/consensus_board.json "
            "or configure a live source. See data/consensus_board_schema.md for the format.",
            file=sys.stderr,
        )
        sys.exit(1)

    with open(SOURCE_FILE, encoding="utf-8") as f:
        try:
            entries = json.load(f)
        except json.JSONDecodeError as exc:
            print(f"Error: data/consensus_board.json is not valid JSON: {exc}", file=sys.stderr)
            sys.exit(1)

    if not entries:
        print(
            "Warning: data/consensus_board.json is empty. "
            "Add entries before running sync_consensus.py. "
            "Existing cache/consensus.json left untouched.",
            file=sys.stderr,
        )
        sys.exit(0)  # not a failure: the board is hand-maintained and the workflow must continue

    # Sort by consensus_rank ascending; ties broken alphabetically by name.
    try:
        sorted_entries = sorted(
            entries,
            key=lambda e: (int(e.get("consensus_rank", 9999)), (e.get("name") or "").lower()),
        )
    except Exception as exc:
        print(f"Error sorting consensus entries: {exc}", file=sys.stderr)
        sys.exit(1)

    payload = {
        "board": sorted_entries,
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }

    cache_dir = os.path.dirname(CACHE_FILE)
    os.makedirs(cache_dir, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=cache_dir, suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        os.replace(tmp, CACHE_FILE)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise

    print(f"cache/consensus.json written ({len(sorted_entries)} entries).")


if __name__ == "__main__":
    main()
