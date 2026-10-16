
import asyncio
import time

from app.services.extractor import InvoiceExtractor
from app.services.exceptions import (
    PermanentExtractionError,
    TransientExtractionError,
)


DOCUMENTS = {
    "invoice_1_valid": """
FACTURA Nº 2026-0412
Proveedor: Laboratorios Ribera S.L.
Fecha: 03/10/2026
Concepto: Reactivos de laboratorio
Base imponible: 1.250,00 EUR
IVA 21%: 262,50 EUR
Total: 1.512,50 EUR
""",
    "invoice_2_valid": """
FACTURA Nº 2026-0413
Proveedor: Suministros Médicos S.A.
Fecha: 04/10/2026
Concepto: Material sanitario
Base imponible: 200,00 EUR
IVA 21%: 42,00 EUR
Total: 242,00 EUR
""",
    "invoice_3_missing_total": """
FACTURA Nº 2026-0414
Proveedor: Sin Total S.L.
Fecha: 05/10/2026
Base imponible: 100,00 EUR
IVA 21%: 21,00 EUR
""",
    "invoice_4_invalid_date": """
FACTURA Nº 2026-0415
Proveedor: Fecha Incorrecta S.L.
Fecha: 31/02/2026
Total: 99,99 EUR
""",
    "invoice_5_invalid_total": """
FACTURA Nº 2026-0416
Proveedor: Importe Incorrecto S.L.
Fecha: 06/10/2026
Total: mil euros
""",
}


async def test_document(name: str, content: str, extractor):
    start = time.perf_counter()

    try:
        result = await extractor.extract(content)

        return {
            "document": name,
            "status": "COMPLETED",
            "supplier": result.supplier,
            "invoice_date": result.invoice_date.isoformat(),
            "total_amount": str(result.total_amount),
            "currency": result.currency,
            "error": None,
            "duration": time.perf_counter() - start,
        }

    except PermanentExtractionError as exc:
        return {
            "document": name,
            "status": "PERMANENT ERROR",
            "supplier": None,
            "invoice_date": None,
            "total_amount": None,
            "currency": None,
            "error": str(exc),
            "duration": time.perf_counter() - start,
        }

    except TransientExtractionError as exc:
        return {
            "document": name,
            "status": "TRANSIENT ERROR (retry not implemented)",
            "supplier": None,
            "invoice_date": None,
            "total_amount": None,
            "currency": None,
            "error": str(exc),
            "duration": time.perf_counter() - start,
        }

    except Exception as exc:
        return {
            "document": name,
            "status": "UNEXPECTED ERROR",
            "supplier": None,
            "invoice_date": None,
            "total_amount": None,
            "currency": None,
            "error": f"{type(exc).__name__}: {exc}",
            "duration": time.perf_counter() - start,
        }


async def main():

    extractor = InvoiceExtractor()

    print("Starting extraction of 5 documents...\n")
    overall_start = time.perf_counter()

    results = await asyncio.gather(
        *[
            test_document(name, content, extractor)
            for name, content in DOCUMENTS.items()
        ]
    )

    for result in results:
        print("=" * 60)
        print(f"Document: {result['document']}")
        print(f"Status:   {result['status']}")
        print(f"Duration: {result['duration']:.2f} seconds")

        if result["supplier"] is not None:
            print(f"Supplier: {result['supplier']}")
            print(f"Date:     {result['invoice_date']}")
            print(f"Total:    {result['total_amount']}")
            print(f"Currency: {result['currency']}")

        if result["error"]:
            print(f"Error:    {result['error']}")

    print("\n" + "=" * 60)
    print(f"Documents tested: {len(results)}")
    print(
        "Completed:       ",
        sum(r["status"] == "COMPLETED" for r in results),
    )
    print(
        "Permanent errors:",
        sum(r["status"] == "PERMANENT ERROR" for r in results),
    )
    print(
        "Transient errors: ",
        sum("TRANSIENT ERROR" in r["status"] for r in results),
    )
    print(
        "Unexpected errors:",
        sum(r["status"] == "UNEXPECTED ERROR" for r in results),
    )
    print(f"Total elapsed: {time.perf_counter() - overall_start:.2f}s")


if __name__ == "__main__":
    asyncio.run(main())