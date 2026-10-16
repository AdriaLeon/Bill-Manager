import asyncio
import logging

from app.services.document_worker import DocumentWorker
from app.services.extractor import InvoiceExtractor


async def main() -> None:
    logging.basicConfig(level=logging.INFO)

    worker = DocumentWorker(extractor=InvoiceExtractor())
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())