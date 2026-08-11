# GitHub Actions Secrets

The following secrets must be configured in the GitHub repository under
**Settings > Secrets and variables > Actions** before workflows will run correctly.

| Secret | Required by | Description |
| --- | --- | --- |
| `CFBD_API_KEY` | `prospect.yml` (`sync_prospects.py`) | Free-tier API key from collegefootballdata.com — sign up at https://collegefootballdata.com/key |

## Secrets NOT required

- **Sleeper API** — no key needed; all Sleeper endpoints are public
- **RotoWire RSS** — no key needed; RSS feed is public

## Adding a secret

1. Go to the repo on GitHub
2. Settings > Secrets and variables > Actions > New repository secret
3. Enter the name exactly as shown above and paste the value
4. Save — the secret is available to workflows as `${{ secrets.SECRET_NAME }}`
