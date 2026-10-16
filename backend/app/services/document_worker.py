
import asyncio
import logging
from uuid import UUID

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.document import Document, DocumentStatus
from app.services.exceptions import (
    PermanentExtractionError,
    TransientExtractionError,
)
from app.services.extractor import InvoiceExtractor

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
BACKOFF_BASE = 1.0
POLL_INTERVAL = 0.5


class DocumentWorker:
    def __init__(self, extractor: InvoiceExtractor) -> None:
        self.extractor = extractor

    def recover_interrupted_documents(self) -> None:
        """Requeue interrupted jobs at worker startup."""
        with SessionLocal.begin() as session:
            session.query(Document).filter(
                Document.status == DocumentStatus.PROCESSING
            ).update(
                {Document.status: DocumentStatus.PENDING},
                synchronize_session=False,
            )

    def claim_next_document(self) -> UUID | None:
        """Atomically claim one pending document."""
        with SessionLocal.begin() as session:
            document = session.execute(
                select(Document)
                .where(Document.status == DocumentStatus.PENDING)
                .order_by(Document.created_at, Document.id)
                .with_for_update(skip_locked=True)
                .limit(1)
            ).scalar_one_or_none()

            if document is None:
                return None

            document.status = DocumentStatus.PROCESSING
            document.attempt_count += 1

            return document.id

    async def process_document(self, document_id: UUID) -> None:
        while True:
            with SessionLocal() as session:
                document = session.get(Document, document_id)

                if document is None:
                    return

                content = document.content
                attempt = document.attempt_count

            try:
                extracted = await self.extractor.extract(content)

            except PermanentExtractionError as exc:
                self._mark_error(document_id, str(exc))
                return

            except TransientExtractionError as exc:
                if attempt >= MAX_ATTEMPTS:
                    self._mark_error(document_id, str(exc))
                    return

                self._save_error(document_id, str(exc))

                await asyncio.sleep(
                    BACKOFF_BASE * (2 ** (attempt - 1))
                )

                # Record the next attempt before invoking the extractor.
                with SessionLocal.begin() as session:
                    document = session.get(Document, document_id)

                    if document is None:
                        return

                    document.attempt_count += 1

                continue

            except Exception as exc:
                logger.exception(
                    "Unexpected extraction error for %s", document_id
                )
                self._mark_error(
                    document_id, f"Error inesperado: {exc}"
                )
                return

            with SessionLocal.begin() as session:
                document = session.get(Document, document_id)

                if document is None:
                    return

                document.supplier = extracted.supplier
                document.invoice_date = extracted.invoice_date
                document.total_amount = extracted.total_amount
                document.currency = extracted.currency
                document.status = DocumentStatus.COMPLETED
                document.last_error = None
                document.processed_at = __import__(
                    "datetime"
                ).datetime.now(
                    __import__("datetime").timezone.utc
                )

            logger.info("Document %s completed", document_id)
            return

    def _save_error(self, document_id: UUID, message: str) -> None:
        with SessionLocal.begin() as session:
            document = session.get(Document, document_id)
            if document is not None:
                document.last_error = message

    def _mark_error(self, document_id: UUID, message: str) -> None:
        from datetime import datetime, timezone

        with SessionLocal.begin() as session:
            document = session.get(Document, document_id)

            if document is not None:
                document.status = DocumentStatus.ERROR
                document.last_error = message
                document.processed_at = datetime.now(timezone.utc)

    async def run(self) -> None:
        self.recover_interrupted_documents()
        logger.info("Document worker started")

        while True:
            document_id = self.claim_next_document()

            if document_id is None:
                await asyncio.sleep(POLL_INTERVAL)
                continue

            try:
                await self.process_document(document_id)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception(
                    "Failed to process document %s", document_id
                )