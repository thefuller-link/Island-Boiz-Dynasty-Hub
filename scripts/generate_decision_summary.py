"""Read data/decisions.json and render site/decisions.md."""

import json
import os
import sys
from datetime import datetime, timedelta, timezone

REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
DECISIONS_FILE = os.path.join(REPO_ROOT, "data", "decisions.json")
OUTPUT_FILE = os.path.join(REPO_ROOT, "site", "decisions.md")

RESPONSE_LABEL = {
    "approve": "approve",
    "veto": "VETO",
    "abstain": "abstain",
    "pending": "(pending)",
}

RESOLUTION_LABEL = {
    "approved": "APPROVED",
    "vetoed": "VETOED",
    "abstained-to-majority": "APPROVED (abstain-to-majority)",
    "auto-approved": "AUTO-APPROVED (deadline)",
    "pending": "pending",
}

APPROVED_STATUSES = {"approved", "abstained-to-majority", "auto-approved"}
DEADLINE_WARN_HOURS = 12


def load_decisions():
    if not os.path.exists(DECISIONS_FILE):
        return None
    with open(DECISIONS_FILE, encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError as exc:
            print(f"Error: {DECISIONS_FILE} is not valid JSON: {exc}", file=sys.stderr)
            sys.exit(1)


def _deadline_tag(entry):
    """Return a deadline tag string for lineup entries, or empty string."""
    if entry.get("type") != "lineup":
        return ""
    deadline_str = entry.get("deadline")
    if not deadline_str:
        return ""
    try:
        deadline = datetime.fromisoformat(deadline_str)
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        if now > deadline:
            return f"  _Deadline: {deadline_str} (deadline passed -- awaiting resolution)_"
        elif (deadline - now) <= timedelta(hours=DEADLINE_WARN_HOURS):
            return f"  _Deadline: {deadline_str} (deadline approaching)_"
        else:
            return f"  _Deadline: {deadline_str}_"
    except ValueError:
        return ""


def render_empty():
    return (
        "# Decision Log\n\n"
        "_No decisions have been logged yet._\n\n"
        "Run `python scripts/log_decision.py` to add the first entry.\n"
    )


def render(entries):
    now = datetime.now(timezone.utc)
    lines = ["# Decision Log", ""]

    awaiting = [
        e for e in entries
        if e.get("resolution") is None or e.get("resolution") == "pending"
    ]
    approved = [e for e in entries if e.get("resolution") in APPROVED_STATUSES]
    vetoed = [e for e in entries if e.get("resolution") == "vetoed"]

    # --- Awaiting Response ---
    lines.append("## Awaiting Response")
    lines.append("")
    if awaiting:
        for e in awaiting:
            waiting = [
                owner for owner, val in e.get("responses", {}).items()
                if val == "pending"
            ]
            desc = e.get("description", "")
            lines.append(f"- **{e['date']}** | {e['type']} | {desc}  ")
            if waiting:
                lines.append(f"  _Waiting on: {', '.join(waiting)}_")
            tag = _deadline_tag(e)
            if tag:
                lines.append(tag)
    else:
        lines.append("_No decisions are currently awaiting a response._")
    lines.append("")

    # --- Approved ---
    lines.append("## Approved")
    lines.append("")
    if approved:
        for e in approved:
            label = RESOLUTION_LABEL.get(e.get("resolution", ""), e.get("resolution", ""))
            reason = e.get("resolution_reason", "")
            responses = e.get("responses", {})
            response_parts = [
                f"{owner}: {RESPONSE_LABEL.get(val, val)}"
                for owner, val in responses.items()
            ]
            lines.append(f"### {e['date']} -- {e['type']}")
            lines.append(f"**Status:** {label}  ")
            if reason:
                lines.append(f"**Reason:** {reason}  ")
            lines.append(f"**Proposed by:** {e.get('proposer', '?')}  ")
            lines.append(f"**Description:** {e.get('description', '')}  ")
            if e.get("rationale"):
                lines.append(f"**Rationale:** {e['rationale']}  ")
            lines.append(f"**Responses:** {' | '.join(response_parts)}")
            lines.append("")
    else:
        lines.append("_No approved decisions yet._")
        lines.append("")

    # --- Vetoed / Blocked ---
    lines.append("## Vetoed / Blocked")
    lines.append("")
    if vetoed:
        for e in vetoed:
            reason = e.get("resolution_reason", "")
            responses = e.get("responses", {})
            response_parts = [
                f"{owner}: {RESPONSE_LABEL.get(val, val)}"
                for owner, val in responses.items()
            ]
            lines.append(f"### {e['date']} -- {e['type']}")
            lines.append(f"**Status:** VETOED  ")
            if reason:
                lines.append(f"**Reason:** {reason}  ")
            lines.append(f"**Proposed by:** {e.get('proposer', '?')}  ")
            lines.append(f"**Description:** {e.get('description', '')}  ")
            if e.get("rationale"):
                lines.append(f"**Rationale:** {e['rationale']}  ")
            lines.append(f"**Responses:** {' | '.join(response_parts)}")
            lines.append("")
    else:
        lines.append("_No vetoed decisions._")
        lines.append("")

    return "\n".join(lines)


def main():
    entries = load_decisions()

    if entries is None or len(entries) == 0:
        md = render_empty()
    else:
        sorted_entries = sorted(
            entries, key=lambda e: e.get("date", ""), reverse=True
        )
        md = render(sorted_entries)

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(md)

    print(f"site/decisions.md written ({len(entries or [])} entries).")


if __name__ == "__main__":
    main()
