"""Pure CSV-upload parser.

parse_csv_upload(file_stream, org_id, upload_id) reads a CSV upload and
returns either:

  - RawResponse    (success: some or all rows parsed; bad rows are skipped
    with a warning instead of failing the whole file)
  - ConnectorError (failure: nothing in the file could be salvaged; carries a
    typed .kind plus .message/.user_message/.retryable, mirroring this
    project's {code, message, user_message, retryable} API error shape)

org_id / upload_id are accepted only to match the call signature used
elsewhere in the project. They are not read or used here, and this function
performs no I/O, no DB/network calls, and no other side effects.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import IO, Any

from ..errors import ConnectorError

REQUIRED_COLUMNS = [
    "date",
    "campaign_name",
    "platform",
    "spend",
    "impressions",
    "clicks",
    "conversions",
    "revenue",
]
OPTIONAL_COLUMNS = ["sessions", "bounces"]

_REQUIRED_FLOAT_FIELDS = ("spend", "revenue")
_REQUIRED_INT_FIELDS = ("impressions", "clicks", "conversions")
_OPTIONAL_INT_FIELDS = ("sessions", "bounces")

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_VALID_PLATFORMS = {"meta", "google"}


class ParseErrorKind(StrEnum):
    """File-level failure codes. Values are unchanged from the original enum."""

    EMPTY_FILE = "empty_file"
    INVALID_HEADER = "invalid_header"
    UNREADABLE_ENCODING = "unreadable_encoding"


@dataclass(frozen=True)
class RawResponse:
    parsed_rows: list[dict[str, Any]] = field(default_factory=list)
    row_count: int = 0
    parse_warnings: list[str] = field(default_factory=list)


def parse_csv_upload(
    file_stream: IO[bytes] | IO[str], org_id: object, upload_id: object
) -> RawResponse | ConnectorError:
    content = file_stream.read()

    if isinstance(content, bytes):
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError as exc:
            return ConnectorError(
                kind=ParseErrorKind.UNREADABLE_ENCODING,
                message=f"File could not be decoded as UTF-8: {exc}",
                user_message=(
                    "We couldn't read this file. Please make sure it's saved as UTF-8 "
                    "and try again."
                ),
                retryable=False,
            )
    else:
        text = content

    # Normalize line endings so csv.reader over an in-memory string doesn't
    # produce spurious blank rows from bare "\r".
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    if text.strip() == "":
        return ConnectorError(
            kind=ParseErrorKind.EMPTY_FILE,
            message="File is empty.",
            user_message=(
                "This file is empty. Please upload a file with a header row "
                "and at least one data row."
            ),
            retryable=False,
        )

    reader = csv.reader(io.StringIO(text))
    try:
        header = next(reader)
    except StopIteration:
        return ConnectorError(
            kind=ParseErrorKind.EMPTY_FILE,
            message="File is empty.",
            user_message=(
                "This file is empty. Please upload a file with a header row "
                "and at least one data row."
            ),
            retryable=False,
        )

    header = [h.strip() for h in header]
    missing_columns = [c for c in REQUIRED_COLUMNS if c not in header]
    if missing_columns:
        missing_list = ", ".join(missing_columns)
        return ConnectorError(
            kind=ParseErrorKind.INVALID_HEADER,
            message=f"Missing required column(s): {missing_list}",
            user_message=(
                f"Your file is missing required column(s): {missing_list}. "
                "Please add them and try again."
            ),
            retryable=False,
        )

    data_rows = [row for row in reader if any(cell.strip() for cell in row)]
    if not data_rows:
        return ConnectorError(
            kind=ParseErrorKind.EMPTY_FILE,
            message="File has a valid header but zero data rows.",
            user_message=(
                "This file has a header row but no data rows. Please add at least one row of data."
            ),
            retryable=False,
        )

    parsed_rows: list[dict[str, Any]] = []
    parse_warnings: list[str] = []

    for row_number, row in enumerate(data_rows, start=2):  # row 1 is the header
        cells = _row_to_cells(header, row)
        cleaned, reasons = _validate_and_clean_row(cells)
        if reasons:
            parse_warnings.append(f"Row {row_number}: {'; '.join(reasons)}")
            continue
        parsed_rows.append(cleaned)

    return RawResponse(
        parsed_rows=parsed_rows,
        row_count=len(parsed_rows),
        parse_warnings=parse_warnings,
    )


def _row_to_cells(header: list[str], row: list[str]) -> dict[str, str]:
    if len(row) < len(header):
        row = row + [""] * (len(header) - len(row))
    elif len(row) > len(header):
        row = row[: len(header)]
    return dict(zip(header, row, strict=True))


def _parse_number(raw: str, kind: str) -> tuple[float | None, str | None]:
    """Returns (value, error) where error is None, 'invalid', or 'negative'."""
    value: float
    try:
        if kind == "int":
            as_float = float(raw)
            if not as_float.is_integer():
                return None, "invalid"
            value = int(as_float)
        else:
            value = float(raw)
    except ValueError:
        return None, "invalid"
    if value < 0:
        return None, "negative"
    return value, None


def _validate_and_clean_row(cells: dict[str, str]) -> tuple[dict[str, Any], list[str]]:
    reasons: list[str] = []
    cleaned: dict[str, Any] = {}

    # date
    date_raw = (cells.get("date") or "").strip()
    if date_raw == "":
        reasons.append("missing required field 'date'")
    elif not _DATE_RE.match(date_raw):
        reasons.append(f"invalid date format '{date_raw}' (expected YYYY-MM-DD)")
    else:
        try:
            datetime.strptime(date_raw, "%Y-%m-%d")
            cleaned["date"] = date_raw
        except ValueError:
            reasons.append(f"invalid date '{date_raw}'")

    # campaign_name
    name_raw = (cells.get("campaign_name") or "").strip()
    if name_raw == "":
        reasons.append("missing required field 'campaign_name'")
    else:
        cleaned["campaign_name"] = name_raw

    # platform
    platform_raw = (cells.get("platform") or "").strip()
    if platform_raw == "":
        reasons.append("missing required field 'platform'")
    elif platform_raw.lower() not in _VALID_PLATFORMS:
        reasons.append(f"invalid platform '{platform_raw}' (expected 'meta' or 'google')")
    else:
        cleaned["platform"] = platform_raw.lower()

    # required numeric fields
    for field_name in _REQUIRED_FLOAT_FIELDS + _REQUIRED_INT_FIELDS:
        raw = (cells.get(field_name) or "").strip()
        if raw == "":
            reasons.append(f"missing required field '{field_name}'")
            continue
        kind = "int" if field_name in _REQUIRED_INT_FIELDS else "float"
        value, err = _parse_number(raw, kind)
        if err == "invalid":
            reasons.append(f"'{field_name}' is not a valid number ('{raw}')")
        elif err == "negative":
            reasons.append(f"'{field_name}' is negative ({raw})")
        else:
            cleaned[field_name] = value

    # optional numeric fields (sessions, bounces) - default 0 when absent/blank
    optional_values: dict[str, float] = {}
    for field_name in _OPTIONAL_INT_FIELDS:
        raw = (cells.get(field_name) or "").strip()
        if raw == "":
            optional_values[field_name] = 0
            continue
        value, err = _parse_number(raw, "int")
        if err == "invalid":
            reasons.append(f"'{field_name}' is not a valid number ('{raw}')")
        elif err == "negative":
            reasons.append(f"'{field_name}' is negative ({raw})")
        elif value is not None:
            optional_values[field_name] = value

    if "sessions" in optional_values and "bounces" in optional_values:
        if optional_values["bounces"] > optional_values["sessions"]:
            reasons.append(
                f"'bounces' ({optional_values['bounces']}) exceeds "
                f"'sessions' ({optional_values['sessions']})"
            )

    if reasons:
        return cleaned, reasons

    cleaned["sessions"] = optional_values.get("sessions", 0)
    cleaned["bounces"] = optional_values.get("bounces", 0)
    return cleaned, []
