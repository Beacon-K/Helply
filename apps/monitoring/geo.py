"""Work out which country a server is in from its public IP address.

The lookup runs entirely on this machine against the DB-IP "country lite" database
(data/dbip-country-lite.mmdb, CC BY 4.0 - https://db-ip.com), so server addresses are never sent to a
third party and it works offline. It only knows countries; the city/region comes from the cloud
provider's own metadata. If the library or the file is missing, detection quietly does nothing.
"""
import ipaddress
import logging
from pathlib import Path

from .countries import COUNTRIES

log = logging.getLogger(__name__)
DATABASE = Path(__file__).resolve().parent / "data" / "dbip-country-lite.mmdb"
_reader = None
_failed = False


def _open():
    global _reader, _failed
    if _reader is None and not _failed:
        try:
            import maxminddb
            _reader = maxminddb.open_database(str(DATABASE))
        except Exception:  # missing file or library: the feature is optional
            log.warning("IP-to-country database unavailable; countries will not be detected", exc_info=True)
            _failed = True
    return _reader


def country_for_ip(ip):
    """Two-letter country code for a public IP address, or "" if it is private or unknown."""
    try:
        address = ipaddress.ip_address((ip or "").strip())
    except ValueError:
        return ""
    if not address.is_global:
        return ""
    reader = _open()
    if reader is None:
        return ""
    try:
        record = reader.get(str(address)) or {}
    except Exception:
        return ""
    code = (record.get("country") or {}).get("iso_code", "")
    return code if code in COUNTRIES else ""
