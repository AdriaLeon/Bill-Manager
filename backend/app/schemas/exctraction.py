from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class ExtractionResult:
    supplier: str
    invoice_date: date
    total_amount: Decimal
    currency: str