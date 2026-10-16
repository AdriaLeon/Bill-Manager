
import asyncio
import random
import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from app.services.exceptions import (PermanentExtractionError,TransientExtractionError)


@dataclass(frozen=True, slots=True)
class ExtractedInvoice:
    supplier: str
    invoice_date: date
    total_amount: Decimal
    currency: str


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

        # Simulate a transient service failure.
        if random.random() < self.failure_rate:
            raise TransientExtractionError(
                "Error temporal simulado del servicio externo"
            )

        return self._parse_invoice(content, total_line)


    @staticmethod
    def _parse_invoice(
        content: str,
        total_line: str,
    ) -> ExtractedInvoice:
        # Spanish amount format: 1.512,50 EUR or EUR 1.512,50.
        amount_pattern = r"-?\d+(?:\.\d{3})*(?:,\d{1,2})?"

        match = re.fullmatch(
            r"\s*Total\b\s*:?\s*"
            r"(?:(?P<currency_before>[A-Z]{3})\s*)?"
            rf"(?P<amount>{amount_pattern})"
            r"\s*(?P<currency_after>[A-Z]{3})?\s*",
            total_line,
            re.IGNORECASE,
        )

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

        normalized_amount = (
            match.group("amount")
            .replace(".", "")
            .replace(",", ".")
        )

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

        supplier_match = re.search(
            r"^\s*Proveedor\s*:\s*(.+?)\s*$",
            content,
            re.IGNORECASE | re.MULTILINE,
        )

        if not supplier_match:
            raise PermanentExtractionError(
                "La factura no contiene el campo Proveedor"
            )

        supplier = supplier_match.group(1).strip()

        date_match = re.search(
            r"^\s*Fecha\s*:\s*"
            r"(?P<date>\d{2}/\d{2}/\d{4}|\d{4}-\d{2}-\d{2})\s*$",
            content,
            re.IGNORECASE | re.MULTILINE,
        )

        if not date_match:
            raise PermanentExtractionError(
                "La factura no contiene una fecha válida"
            )

        date_text = date_match.group("date")

        try:
            if "/" in date_text:
                invoice_date = datetime.strptime(
                    date_text, "%d/%m/%Y"
                ).date()
            else:
                invoice_date = date.fromisoformat(date_text)
        except ValueError as exc:
            raise PermanentExtractionError(
                f"Fecha de factura no válida: {date_text}"
            ) from exc

        return ExtractedInvoice(
            supplier=supplier,
            invoice_date=invoice_date,
            total_amount=amount,
            currency=currency.upper(),
        )