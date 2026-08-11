"""Compute and write resolution status for all entries in data/decisions.json."""

import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone

import yaml

REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
CONFIG_FILE = os.path.join(REPO_ROOT, "config.yaml")
DECISIONS_FILE = os.path.join(REPO_ROOT, "data", "decisions.json")
SLEEPER_CACHE = os.path.join(REPO_ROOT, "cache", "sleeper.json")
KTC_CACHE = os.path.join(REPO_ROOT, "cache", "ktc.json")

OUR_ROSTER_ID = 2

APPROVED_STATUSES = {"approved", "abstained-to-majority", "auto-approved"}


def _load_config():
    with open(CONFIG_FILE, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    owners = cfg.get("owners", [])
    if not owners:
        print("Error: 'owners' key missing from config.yaml.", file=sys.stderr)
        sys.exit(1)
    return [str(o) for o in owners]


def _load_decisions():
    if not os.path.exists(DECISIONS_FILE):
        return []
    with open(DECISIONS_FILE, encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError as exc:
            print(f"Error: decisions.json is not valid JSON: {exc}", file=sys.stderr)
            sys.exit(1)


def _save_decisions(entries):
    os.makedirs(os.path.dirname(DECISIONS_FILE), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(DECISIONS_FILE), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(entries, f, indent=2)
            f.write("\n")
        os.replace(tmp, DECISIONS_FILE)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _normalize(text):
    text = text.lower()
    text = re.sub(r"[^a-z0-9 ]", "", text)
    return re.sub(r"\s+", " ", text).strip()


# --- Resolution logic helpers ---

def _is_resolved(entry):
    """Return True if entry already has a final (non-pending) resolution."""
    res = entry.get("resolution")
    return res is not None and res != "pending"


def _majority_resolution(responses, owners):
    """
    Return (resolution, reason) using majority (2/3) rule.
    Handles abstain-to-majority when exactly one owner abstains.
    """
    approvals = [o for o in owners if responses.get(o) == "approve"]
    vetoes = [o for o in owners if responses.get(o) == "veto"]
    abstains = [o for o in owners if responses.get(o) == "abstain"]
    pending = [o for o in owners if responses.get(o) == "pending"]

    # Two explicit approvals — resolved
    if len(approvals) >= 2:
        return ("approved", f"majority approved ({', '.join(approvals)})")

    # Two explicit vetoes — resolved
    if len(vetoes) >= 2:
        return ("vetoed", f"majority vetoed ({', '.join(vetoes)})")

    # Abstain-to-majority: exactly one abstain, other two agree
    if len(abstains) == 1 and len(pending) == 0:
        non_abstain = [o for o in owners if responses.get(o) != "abstain"]
        votes = [responses.get(o) for o in non_abstain]
        if votes.count("approve") == 2:
            return ("approved", f"abstain-to-majority ({non_abstain[0]} and {non_abstain[1]} approved; {abstains[0]} abstained)")
        if votes.count("veto") == 2:
            return ("vetoed", f"abstain-to-majority ({non_abstain[0]} and {non_abstain[1]} vetoed; {abstains[0]} abstained)")

    waiting = pending + abstains if not pending else pending
    return ("pending", f"waiting on: {', '.join(pending)}" if pending else "awaiting responses")


def _unanimous_resolution(responses, owners, reason_prefix="unanimous"):
    """Return (resolution, reason) requiring all owners to approve."""
    vetoing = [o for o in owners if responses.get(o) == "veto"]
    pending = [o for o in owners if responses.get(o) == "pending"]
    approvals = [o for o in owners if responses.get(o) == "approve"]

    if vetoing:
        return ("vetoed", f"{reason_prefix}: {vetoing[0]} vetoed (protected asset)")
    if pending:
        return ("pending", f"waiting on: {', '.join(pending)} (unanimous required)")
    if len(approvals) == len(owners):
        return ("approved", f"{reason_prefix}: all owners approved")
    return ("pending", f"waiting on responses (unanimous required)")


# --- Top-3 player and pick detection ---

def _load_top3_players():
    """
    Return list of up to 3 normalized player names for our team (roster_id=2)
    sorted by KTC value descending. Returns None if caches are unavailable.
    """
    if not os.path.exists(SLEEPER_CACHE) or not os.path.exists(KTC_CACHE):
        return None
    try:
        with open(SLEEPER_CACHE, encoding="utf-8") as f:
            sleeper = json.load(f)
        with open(KTC_CACHE, encoding="utf-8") as f:
            ktc = json.load(f)
    except Exception:
        return None

    # Find our team's player IDs
    our_players = []
    for uid, roster in sleeper.get("rosters", {}).items():
        if roster.get("roster_id") == OUR_ROSTER_ID:
            our_players = roster.get("players") or []
            break

    player_metadata = sleeper.get("player_metadata", {})
    ktc_by_name = {p["name_key"]: p["value"] for p in ktc.get("players", [])}

    # Build (normalized_name, ktc_value) pairs
    scored = []
    for pid in our_players:
        meta = player_metadata.get(str(pid)) or player_metadata.get(pid)
        if not meta:
            continue
        full_name = meta.get("full_name", "")
        if not full_name:
            continue
        norm = _normalize(full_name)
        value = ktc_by_name.get(norm, 0)
        scored.append((norm, value))

    scored.sort(key=lambda x: x[1], reverse=True)
    return [name for name, _ in scored[:3]]


def _requires_unanimous(description, top3_names):
    """
    Return True if the decision requires unanimous approval.
    Returns True when: top3_names is None (safe fallback), OR description
    mentions a top-3 roster player, OR description matches the 1st-round pick pattern.
    """
    if top3_names is None:
        return True  # Safe fallback: apply unanimous when caches unavailable

    norm_desc = _normalize(description)

    # Top-3 player substring check
    for name in top3_names:
        if name and name in norm_desc:
            return True

    # Future 1st-round pick pattern
    has_first = "1st" in norm_desc
    has_year_or_pick = any(token in norm_desc for token in ("2026", "2027", "2028", "pick"))
    if has_first and has_year_or_pick:
        return True

    return False


# --- Main resolution loop ---

def _resolve_entry(entry, owners, top3_names):
    """
    Compute and return (resolution, reason) for a single entry.
    Does NOT mutate the entry.
    """
    responses = entry.get("responses", {})

    # Lineup deadline auto-resolution (check before voting logic)
    if entry.get("type") == "lineup":
        deadline_str = entry.get("deadline")
        if deadline_str:
            try:
                deadline = datetime.fromisoformat(deadline_str)
                if deadline.tzinfo is None:
                    deadline = deadline.replace(tzinfo=timezone.utc)
                now = datetime.now(timezone.utc)
                if now > deadline:
                    pending = [o for o in owners if responses.get(o) == "pending"]
                    if pending:
                        return (
                            "auto-approved",
                            "auto-resolved by deadline - not all owners responded",
                        )
            except ValueError:
                pass  # Malformed deadline — fall through to voting logic

    description = entry.get("description", "")
    if _requires_unanimous(description, top3_names):
        reason_prefix = "unanimous (cache unavailable)" if top3_names is None else "unanimous"
        return _unanimous_resolution(responses, owners, reason_prefix)
    else:
        return _majority_resolution(responses, owners)


def main():
    owners = _load_config()
    entries = _load_decisions()

    if not entries:
        print("No decisions to resolve.")
        return

    top3_names = _load_top3_players()
    if top3_names is None:
        print("Warning: KTC/Sleeper cache unavailable — applying unanimous rule as safe fallback.")
    else:
        print(f"Top-3 roster players (unanimous trigger): {', '.join(top3_names) or 'none found'}")

    changed = 0
    for entry in entries:
        if _is_resolved(entry):
            continue  # Immutable — skip

        resolution, reason = _resolve_entry(entry, owners, top3_names)
        entry["resolution"] = resolution
        entry["resolution_reason"] = reason
        changed += 1

    _save_decisions(entries)
    resolved_count = sum(1 for e in entries if e.get("resolution") not in (None, "pending"))
    print(
        f"resolve_decisions: {changed} entries processed, "
        f"{resolved_count} total resolved in decisions.json."
    )


if __name__ == "__main__":
    main()
