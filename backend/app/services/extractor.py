
import asyncio
import random
import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from app.services.exceptions import (
    PermanentExtractionError,
    TransientExtractionError,
)


@dataclass(frozen=True, slots=True)
class ExtractedInvoice:
    supplier: str | None = None
    invoice_date: date | None = None
    total_amount: Decimal | None = None
    currency: str | None = None


class InvoiceExtractor:
    def __init__(
        self,
        failure_rate: float = 0.20,
        min_latency: float = 1.0,
        max_latency: float = 4.0,
        max_attempts: int = 3,
        backoff_base: float = 1.0,
    ) -> None:
        if not 0 <= failure_rate <= 1:
            raise ValueError("failure_rate must be between 0 and 1")
        if min_latency < 0 or max_latency < min_latency:
            raise ValueError("Invalid latency range")
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if backoff_base < 0:
            raise ValueError("backoff_base must be non-negative")

        self.failure_rate = failure_rate
        self.min_latency = min_latency
        self.max_latency = max_latency
        self.max_attempts = max_attempts
        self.backoff_base = backoff_base

    async def extract(self, content: str) -> ExtractedInvoice:
        # Total is mandatory. Missing total is never retryable.
        total_line = next(
            (
                line.strip()
                for line in content.splitlines()
                if re.match(r"^\s*Total\b", line, re.IGNORECASE)
            ),
            None,
        )

        if total_line is None:
            raise PermanentExtractionError(
                "La factura no contiene una línea Total"
            )

        # Simulate one external service request.
        await asyncio.sleep(
            random.uniform(self.min_latency, self.max_latency)
        )

        if random.random() < self.failure_rate:
            raise TransientExtractionError(
                "Error temporal simulado del servicio externo"
            )

        return self._parse_invoice(content, total_line)

    @staticmethod
    def _parse_invoice(
        content: str, total_line: str
    ) -> ExtractedInvoice:
        amount_pattern = r"\d+(?:\.\d{3})*(?:,\d{1,2})?"

        match = re.fullmatch(
            r"\s*Total\b\s*:?\s*"
            r"(?:(?P<currency_before>[A-Z]{3})\s*)?"
            rf"(?P<amount>{amount_pattern})"
            r"\s*(?P<currency_after>[A-Z]{3})?\s*",
            total_line,
            re.IGNORECASE,
        )

        # An unparseable total is a permanent failure.
        if not match:
            raise PermanentExtractionError(
                f"No se pudo interpretar el importe total: {total_line}"
            )

        currency = (
            match.group("currency_before")
            or match.group("currency_after")
        )

        if not currency:
            raise PermanentExtractionError(
                "El importe total no especifica la moneda"
            )

        raw_amount = match.group("amount")

        if "," in raw_amount:
            normalized_amount = (
                raw_amount.replace(".", "").replace(",", ".")
            )
        elif "." in raw_amount:
            if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", raw_amount):
                normalized_amount = raw_amount.replace(".", "")
            else:
                normalized_amount = raw_amount
        else:
            normalized_amount = raw_amount

        try:
            amount = Decimal(normalized_amount)
        except InvalidOperation as exc:
            raise PermanentExtractionError(
                "El importe total no es válido"
            ) from exc

        if not amount.is_finite() or amount < 0:
            raise PermanentExtractionError(
                "El importe total debe ser un número finito no negativo"
            )

        # Extract other fields independently.
        missing_fields: list[str] = []

        supplier_match = re.search(
            r"^\s*Proveedor\s*:\s*(.+?)\s*$",
            content,
            re.IGNORECASE | re.MULTILINE,
        )
        supplier = (
            supplier_match.group(1).strip()
            if supplier_match and supplier_match.group(1).strip()
            else None
        )

        if supplier is None:
            missing_fields.append("Proveedor")

        date_match = re.search(
            r"^\s*Fecha\s*:\s*"
            r"(?P<date>"
            r"\d{4}-\d{2}-\d{2}"
            r"|\d{1,2}[/-]\d{1,2}[/-]\d{4}"
            r")\s*$",
            content,
            re.IGNORECASE | re.MULTILINE,
        )

        invoice_date = None

        if date_match:
            date_text = date_match.group("date")
            try:
                if re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_text):
                    invoice_date = date.fromisoformat(date_text)
                else:
                    date_format = (
                        "%d/%m/%Y"
                        if "/" in date_text
                        else "%d-%m-%Y"
                    )
                    invoice_date = datetime.strptime(
                        date_text, date_format
                    ).date()
            except ValueError:
                pass

        if invoice_date is None:
            missing_fields.append("Fecha")

        extracted = ExtractedInvoice(
            supplier=supplier,
            invoice_date=invoice_date,
            total_amount=amount,
            currency=currency.upper(),
        )

        if missing_fields:
            raise TransientExtractionError(
                "Faltan campos obligatorios: "
                + ", ".join(missing_fields),
                partial_data=extracted,
            )

        return extracted