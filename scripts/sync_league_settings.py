"""Fetch league settings from Sleeper and write cache/league_settings.json."""

import json
import os
import sys
import tempfile
from datetime import datetime, timezone

import requests
import yaml

REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
CONFIG_FILE = os.path.join(REPO_ROOT, "config.yaml")
OUTPUT_FILE = os.path.join(REPO_ROOT, "cache", "league_settings.json")

SLEEPER_API = "https://api.sleeper.app/v1/league/{league_id}"
TIMEOUT = 10


def main():
    with open(CONFIG_FILE, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    league_id = cfg.get("league_id")
    if not league_id:
        print("Error: 'league_id' missing from config.yaml.", file=sys.stderr)
        sys.exit(1)

    url = SLEEPER_API.format(league_id=league_id)
    print(f"Fetching league settings from {url}")
    try:
        resp = requests.get(url, timeout=TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.Timeout:
        print(f"Error: request to {url} timed out after {TIMEOUT}s.", file=sys.stderr)
        sys.exit(1)
    except requests.exceptions.HTTPError as exc:
        print(f"Error: HTTP {exc.response.status_code} from Sleeper API: {exc}", file=sys.stderr)
        sys.exit(1)
    except requests.exceptions.RequestException as exc:
        print(f"Error: network error fetching league settings: {exc}", file=sys.stderr)
        sys.exit(1)

    data["last_updated"] = datetime.now(timezone.utc).isoformat()

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(OUTPUT_FILE), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
        os.replace(tmp, OUTPUT_FILE)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise

    scoring = data.get("scoring_settings", {})
    settings = data.get("settings", {})
    print(
        f"sync_league_settings: cached league '{data.get('name', league_id)}' "
        f"(scoring keys: {len(scoring)}, max_keepers: {settings.get('max_keepers', 'N/A')})"
    )


if __name__ == "__main__":
    main()
