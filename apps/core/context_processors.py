from django.conf import settings

ASSET_FILES = ("css/app.css", "css/monitoring.css", "css/theme.css", "js/theme.js", "js/notifications.js", "js/kb-vote.js", "js/live.js",
               "js/fleet.js", "js/fleet-detail.js")


def asset_version(request):
    """A version stamp for CSS/JS URLs (?v=...). It changes whenever one of the files changes,
    so browsers download the new version instead of reusing an old cached copy."""
    stamps = []
    for name in ASSET_FILES:
        path = settings.BASE_DIR / "static" / name
        if path.exists():
            stamps.append(int(path.stat().st_mtime))
    return {"asset_version": max(stamps, default=0)}
