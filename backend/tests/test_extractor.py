from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from app.services.exceptions import PermanentExtractionError
from app.services.extractor import InvoiceExtractor

from app.services.exceptions import (PermanentExtractionError,TransientExtractionError)


FIXTURES = Path(__file__).parent / "samples"


@pytest.fixture
def extractor():
    return InvoiceExtractor(
        failure_rate=0,
        min_latency=0,
        max_latency=0,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("filename", "expected_amount"),
    [
        ("valid-integer-amount.txt", Decimal("1234")),
        ("valid-european-thousands.txt", Decimal("1512.50")),
        ("valid-decimal-cents.txt", Decimal("250.50")),
    ],
)
async def test_extracts_supported_amount_formats(
    extractor,
    filename,
    expected_amount,
):
    content = (FIXTURES / filename).read_text(encoding="utf-8")

    result = await extractor.extract(content)

    assert result.total_amount == expected_amount


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("filename", "expected_message"),
    [
        ("invalid-malformed-amount.txt", "importe"),
        ("invalid-us-thousands.txt", "importe"),
    ],
)
async def test_rejects_malformed_amount_formats(
    extractor,
    filename,
    expected_message,
):
    content = (FIXTURES / filename).read_text(encoding="utf-8")

    with pytest.raises(PermanentExtractionError) as exc_info:
        await extractor.extract(content)

    assert expected_message.casefold() in str(exc_info.value).casefold()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("filename", "expected_date"),
    [
        ("valid-date-dmy-hyphen.txt", date(2004, 12, 1)),
        ("valid-date-dmy-slash-single-digit.txt", date(2004, 12, 1)),
        ("valid-date-dmy-slash.txt", date(2004, 12, 1)),
        ("valid-date-iso.txt", date(2004, 12, 1)),
    ],
)
async def test_extracts_supported_date_formats(
    extractor,
    filename,
    expected_date,
):
    content = (FIXTURES / filename).read_text(encoding="utf-8")

    result = await extractor.extract(content)

    assert result.invoice_date == expected_date
    

@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("filename", "expected_message"),
    [
        ("invalid-date-us-format.txt", "fecha"),
    ],
)
async def test_retries_invalid_date_formats(
    extractor,
    filename,
    expected_message,
):
    content = (FIXTURES / filename).read_text(encoding="utf-8")

    with pytest.raises(TransientExtractionError) as exc_info:
        await extractor.extract(content)

    assert expected_message.casefold() in str(exc_info.value).casefold()

    # The valid fields should be preserved as partial data.
    partial = exc_info.value.partial_data
    assert partial is not None
    assert partial.invoice_date is None
    assert partial.total_amount is not None