"""Number formatting shared by templates."""


def human_rate(value):
    """Bytes per second -> '1.2 MB/s'."""
    if value is None:
        return "–"
    for unit in ("B/s", "KB/s", "MB/s", "GB/s"):
        if abs(value) < 1024 or unit == "GB/s":
            return f"{value:.0f} {unit}" if unit == "B/s" else f"{value:.1f} {unit}"
        value /= 1024
