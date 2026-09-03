import re
from datetime import date, datetime

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Provider-specific status translations; CSV currently has no status values.
_STATUS_MAP: dict[str, dict[str, str]] = {
    "csv_demo": {},
}


def map_platform(provider: str, platform_raw: str | None) -> str | None:
    if platform_raw is None:
        return None

    platform = platform_raw.strip().lower()

    if platform in {"meta", "google"}:
        return platform

    return None


def map_status(provider: str, status_raw: str | None) -> str | None:
    if status_raw is None:
        return None

    status = status_raw.strip().lower()
    return _STATUS_MAP.get(provider, {}).get(status)


def map_external_id(external_id_raw: str | None) -> str | None:
    if external_id_raw is None:
        return None

    external_id = external_id_raw.strip()
    return external_id or None


def parse_iso_date(raw: str | None) -> date | None:
    if raw is None or not _DATE_RE.match(raw):
        return None

    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return None
