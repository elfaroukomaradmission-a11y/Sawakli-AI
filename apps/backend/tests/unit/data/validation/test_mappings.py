from datetime import date

from sawakli.data.validation.mappings import (
    map_external_id,
    map_platform,
    map_status,
    parse_iso_date,
)


def test_map_platform() -> None:
    cases = [
        ("meta", "meta"),
        ("google", "google"),
        ("META", "meta"),
        (" Google ", "google"),
        ("tiktok", None),
        (None, None),
    ]

    for raw, expected in cases:
        assert map_platform("csv_demo", raw) == expected


def test_map_status() -> None:
    cases = [
        (None, None),
        ("ACTIVE", None),
        ("paused", None),
        ("unknown_status", None),
    ]

    for raw, expected in cases:
        assert map_status("csv_demo", raw) == expected


def test_map_external_id() -> None:
    cases = [
        ("abc123", "abc123"),
        ("  abc123  ", "abc123"),
        ("", None),
        ("   ", None),
        (None, None),
    ]

    for raw, expected in cases:
        assert map_external_id(raw) == expected


def test_parse_iso_date() -> None:
    cases = [
        ("2026-05-23", date(2026, 5, 23)),
        ("2026-02-31", None),
        ("23-05-2026", None),
        ("2026/05/23", None),
        ("", None),
        (None, None),
    ]

    for raw, expected in cases:
        assert parse_iso_date(raw) == expected
