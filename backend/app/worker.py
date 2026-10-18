import asyncio
import logging
import os

from dotenv import load_dotenv

from app.services.document_worker import DocumentWorker
from app.services.extractor import InvoiceExtractor
from app.services.gemini_invoice_extractor import GeminiInvoiceExtractor


async def main() -> None:
    load_dotenv()
    logging.basicConfig(level=logging.INFO)

    use_ai = os.getenv("USE_AI_EXTRACTOR", "false").lower() in {"true","1","yes"}

    if use_ai:
        worker = DocumentWorker(extractor=GeminiInvoiceExtractor())
    else:
        worker = DocumentWorker(extractor=InvoiceExtractor())
        
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())