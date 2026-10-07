"""Shared HTML rendering utilities for site-shell page generators."""

from datetime import datetime, timezone

NAV_LINKS = [
    ("today",     "index.html",    "&#127968;", "Today"),
    ("rookies",   "rookies.html",  "&#128640;", "Rookies &amp; Picks"),
    ("trades",    "trades.html",   "&#128260;", "Trades"),
]


def page_shell(title, active_tab, body_html):
    """Return a full HTML page string wrapping body_html in the site shell."""
    nav_items = []
    for tab_id, href, icon, label in NAV_LINKS:
        cls = ' class="active"' if tab_id == active_tab else ""
        nav_items.append(
            f'    <a href="{href}"{cls}>'
            f'<span class="nav-icon">{icon}</span> {label}</a>'
        )
    nav_html = "\n".join(nav_items)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} | IslandBoiiiiiz Hub</title>
  <link rel="stylesheet" href="static/style.css">
</head>
<body>
<nav class="site-nav">
{nav_html}
</nav>
<div class="page-container">
{body_html}
</div>
</body>
</html>"""


def stale_banner(label, timestamp_str, threshold_hours=24):
    """Return a warning banner HTML string if timestamp_str is stale or None."""
    if timestamp_str is None:
        return f'<div class="banner-warn">&#9888; {label} data not yet synced.</div>\n'
    try:
        ts = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        age_hours = (datetime.now(timezone.utc) - ts).total_seconds() / 3600
        if age_hours > threshold_hours:
            ts_str = ts.strftime("%Y-%m-%d %H:%M UTC")
            return (
                f'<div class="banner-warn">&#9888; {label} data may be stale '
                f'(last synced: {ts_str}).</div>\n'
            )
    except (ValueError, TypeError):
        return f'<div class="banner-warn">&#9888; {label} timestamp could not be parsed.</div>\n'
    return ""


def missing_section(label):
    """Return a placeholder HTML string for a cache file that is absent."""
    return f'<p class="banner-missing">No {label} data available yet.</p>\n'


def _atomic_write(path, content):
    import os
    import tempfile
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
