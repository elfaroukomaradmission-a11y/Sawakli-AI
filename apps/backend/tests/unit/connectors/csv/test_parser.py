import io

from sawakli.connectors.csv.parser import ParseErrorKind, RawResponse, parse_csv_upload
from sawakli.connectors.errors import ConnectorError

ORG_ID = "org_123"
UPLOAD_ID = "upload_456"

HEADER = "date,campaign_name,platform,spend,impressions,clicks,conversions,revenue,sessions,bounces"


def make_stream(text: str) -> io.BytesIO:
    """Build an upload-like binary stream, the way a real upload arrives."""
    return io.BytesIO(text.encode("utf-8"))


def test_fully_valid_file():
    csv_text = (
        HEADER + "\n"
        "2024-01-15,Spring Sale,meta,100.50,1000,50,5,250.00,300,20\n"
        "2024-01-16,Summer Blast,google,200.00,2000,80,10,500.00,400,30\n"
    )

    result = parse_csv_upload(make_stream(csv_text), ORG_ID, UPLOAD_ID)

    assert isinstance(result, RawResponse)
    assert result.row_count == 2
    assert result.parse_warnings == []
    assert result.parsed_rows[0] == {
        "date": "2024-01-15",
        "campaign_name": "Spring Sale",
        "platform": "meta",
        "spend": 100.50,
        "impressions": 1000,
        "clicks": 50,
        "conversions": 5,
        "revenue": 250.00,
        "sessions": 300,
        "bounces": 20,
    }
    assert result.parsed_rows[1]["platform"] == "google"


def test_one_bad_row_negative_spend_still_succeeds_with_warning():
    csv_text = (
        HEADER + "\n"
        "2024-01-15,Spring Sale,meta,100.50,1000,50,5,250.00,300,20\n"
        "2024-01-16,Broken Row,google,-50.00,2000,80,10,500.00,400,30\n"
        "2024-01-17,Autumn Push,meta,75.00,1500,60,8,300.00,350,15\n"
    )

    result = parse_csv_upload(make_stream(csv_text), ORG_ID, UPLOAD_ID)

    assert isinstance(result, RawResponse)
    assert result.row_count == 2
    assert len(result.parse_warnings) == 1
    assert "Row 3" in result.parse_warnings[0]
    assert "spend" in result.parse_warnings[0]
    campaign_names = [row["campaign_name"] for row in result.parsed_rows]
    assert "Broken Row" not in campaign_names
    assert campaign_names == ["Spring Sale", "Autumn Push"]


def test_bounces_greater_than_sessions_is_skipped_with_warning():
    csv_text = (
        HEADER + "\n"
        "2024-01-15,Spring Sale,meta,100.50,1000,50,5,250.00,300,20\n"
        "2024-01-16,Bad Bounces,google,200.00,2000,80,10,500.00,10,50\n"
    )

    result = parse_csv_upload(make_stream(csv_text), ORG_ID, UPLOAD_ID)

    assert isinstance(result, RawResponse)
    assert result.row_count == 1
    assert len(result.parse_warnings) == 1
    assert "Row 3" in result.parse_warnings[0]
    assert "bounces" in result.parse_warnings[0]
    assert result.parsed_rows[0]["campaign_name"] == "Spring Sale"


def test_empty_file_header_only_no_data_rows():
    csv_text = HEADER + "\n"

    result = parse_csv_upload(make_stream(csv_text), ORG_ID, UPLOAD_ID)

    assert isinstance(result, ConnectorError)
    assert result.kind == ParseErrorKind.EMPTY_FILE
    assert result.retryable is False
    assert result.message
    assert result.user_message


def test_truly_empty_file():
    result = parse_csv_upload(make_stream(""), ORG_ID, UPLOAD_ID)

    assert isinstance(result, ConnectorError)
    assert result.kind == ParseErrorKind.EMPTY_FILE
    assert result.retryable is False
    assert result.message
    assert result.user_message


def test_missing_required_column_in_header():
    # "revenue" column is missing entirely.
    bad_header = "date,campaign_name,platform,spend,impressions,clicks,conversions,sessions,bounces"
    csv_text = bad_header + "\n2024-01-15,Spring Sale,meta,100.50,1000,50,5,300,20\n"

    result = parse_csv_upload(make_stream(csv_text), ORG_ID, UPLOAD_ID)

    assert isinstance(result, ConnectorError)
    assert result.kind == ParseErrorKind.INVALID_HEADER
    assert result.retryable is False
    # message should name the specific missing column, not just say "invalid".
    assert "revenue" in result.message
    assert "revenue" in result.user_message


def test_badly_encoded_file_is_unreadable_encoding():
    # Latin-1 encoded bytes containing a byte sequence that is not valid UTF-8.
    csv_text = HEADER + "\n" + "2024-01-15,Café Münster,meta,100.50,1000,50,5,250.00,300,20\n"
    bad_bytes = csv_text.encode("latin-1")

    result = parse_csv_upload(io.BytesIO(bad_bytes), ORG_ID, UPLOAD_ID)

    assert isinstance(result, ConnectorError)
    assert result.kind == ParseErrorKind.UNREADABLE_ENCODING
    assert result.retryable is False
    # message should carry the actual decode error, not a generic string.
    assert "utf-8" in result.message.lower() or "decode" in result.message.lower()
    assert result.user_message


def test_org_id_and_upload_id_are_not_required_to_be_meaningful():
    # Function must be pure: passing None/garbage for org_id/upload_id must not
    # affect behavior, since they are only accepted for signature parity.
    csv_text = HEADER + "\n" + "2024-01-15,Spring Sale,meta,100.50,1000,50,5,250.00,300,20\n"

    result = parse_csv_upload(make_stream(csv_text), None, None)

    assert isinstance(result, RawResponse)
    assert result.row_count == 1


def test_stringio_input_also_works():
    # file_stream can be text-mode (io.StringIO) as well as binary (io.BytesIO).
    csv_text = HEADER + "\n" + "2024-01-15,Spring Sale,meta,100.50,1000,50,5,250.00,300,20\n"

    result = parse_csv_upload(io.StringIO(csv_text), ORG_ID, UPLOAD_ID)

    assert isinstance(result, RawResponse)
    assert result.row_count == 1


def test_optional_columns_default_when_absent_from_header():
    header_without_optional = (
        "date,campaign_name,platform,spend,impressions,clicks,conversions,revenue"
    )
    csv_text = header_without_optional + "\n2024-01-15,Spring Sale,meta,100.50,1000,50,5,250.00\n"

    result = parse_csv_upload(make_stream(csv_text), ORG_ID, UPLOAD_ID)

    assert isinstance(result, RawResponse)
    assert result.row_count == 1
    assert result.parsed_rows[0]["sessions"] == 0
    assert result.parsed_rows[0]["bounces"] == 0


def test_missing_required_value_in_row_is_warned_and_skipped():
    csv_text = (
        HEADER + "\n"
        ",Missing Date,meta,100.50,1000,50,5,250.00,300,20\n"
        "2024-01-16,Spring Sale,meta,100.50,1000,50,5,250.00,300,20\n"
    )

    result = parse_csv_upload(make_stream(csv_text), ORG_ID, UPLOAD_ID)

    assert isinstance(result, RawResponse)
    assert result.row_count == 1
    assert len(result.parse_warnings) == 1
    assert "Row 2" in result.parse_warnings[0]
    assert "date" in result.parse_warnings[0]


def test_invalid_date_format_is_warned_and_skipped():
    csv_text = (
        HEADER + "\n"
        "01/15/2024,Bad Date,meta,100.50,1000,50,5,250.00,300,20\n"
        "2024-01-16,Spring Sale,meta,100.50,1000,50,5,250.00,300,20\n"
    )

    result = parse_csv_upload(make_stream(csv_text), ORG_ID, UPLOAD_ID)

    assert isinstance(result, RawResponse)
    assert result.row_count == 1
    assert "Row 2" in result.parse_warnings[0]


def test_invalid_platform_is_warned_and_skipped():
    csv_text = (
        HEADER + "\n"
        "2024-01-15,Bad Platform,tiktok,100.50,1000,50,5,250.00,300,20\n"
        "2024-01-16,Spring Sale,meta,100.50,1000,50,5,250.00,300,20\n"
    )

    result = parse_csv_upload(make_stream(csv_text), ORG_ID, UPLOAD_ID)

    assert isinstance(result, RawResponse)
    assert result.row_count == 1
    assert "Row 2" in result.parse_warnings[0]
    assert "platform" in result.parse_warnings[0]


def test_non_numeric_value_is_warned_and_skipped():
    csv_text = (
        HEADER + "\n"
        "2024-01-15,Bad Number,meta,abc,1000,50,5,250.00,300,20\n"
        "2024-01-16,Spring Sale,meta,100.50,1000,50,5,250.00,300,20\n"
    )

    result = parse_csv_upload(make_stream(csv_text), ORG_ID, UPLOAD_ID)

    assert isinstance(result, RawResponse)
    assert result.row_count == 1
    assert "Row 2" in result.parse_warnings[0]
    assert "spend" in result.parse_warnings[0]
