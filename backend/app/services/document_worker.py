
import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select, update

from app.db.session import SessionLocal
from app.models.document import Document, DocumentStatus
from app.services.exceptions import (PermanentExtractionError,TransientExtractionError)
from app.services.extractor import InvoiceExtractor

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
BACKOFF_BASE = 1.0
POLL_INTERVAL = 0.5

LEASE_DURATION = timedelta(seconds=60)
LEASE_RENEW_INTERVAL = 20

EXTRACTED_FIELDS = (
    "supplier",
    "invoice_date",
    "total_amount",
    "currency",
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class DocumentWorker:
    def __init__(self,extractor: InvoiceExtractor | None = None) -> None:
        self.extractor = extractor or InvoiceExtractor()

        logger.info(
            "Document worker initialized with %s extractor",
            type(self.extractor).__name__,
        )

    def recover_stale_documents(self) -> None:
        """Recover jobs whose processing leases have expired."""
        now = utc_now()

        with SessionLocal.begin() as session:
            stale_documents = session.scalars(
                select(Document)
                .where(
                    Document.status == DocumentStatus.PROCESSING,
                    Document.lease_expires_at <= now,
                )
                .with_for_update(skip_locked=True)
            ).all()

            for document in stale_documents:
                message = "Processing lease expired; job recovered."

                if document.attempt_count >= MAX_ATTEMPTS:
                    document.status = DocumentStatus.ERROR
                    document.processed_at = now
                    document.last_error = (
                        "Processing lease expired after maximum attempts."
                    )
                else:
                    document.status = DocumentStatus.PENDING
                    document.last_error = message

                document.lease_token = None
                document.lease_expires_at = None

                logger.warning(
                    "Recovered stale document %s (attempt %s)",
                    document.id,
                    document.attempt_count,
                )


    def claim_next_document(self) -> tuple[UUID, UUID] | None:
        """Atomically claim a pending document and create its lease."""
        now = utc_now()
        token = uuid.uuid4()

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
            document.lease_token = token
            document.lease_expires_at = now + LEASE_DURATION
            document.last_error = None

            document_id = document.id

        logger.info("Claimed document %s", document_id)
        return document_id, token


    def renew_lease(self, document_id: UUID, token: UUID) -> bool:
        """Renew only if this worker still owns a valid lease."""
        now = utc_now()

        with SessionLocal.begin() as session:
            result = session.execute(
                update(Document)
                .where(
                    Document.id == document_id,
                    Document.status == DocumentStatus.PROCESSING,
                    Document.lease_token == token,
                    Document.lease_expires_at > now,
                )
                .values(lease_expires_at=now + LEASE_DURATION)
            )

            return result.rowcount == 1


    async def _heartbeat(
        self,
        document_id: UUID,
        token: UUID,
        stop_event: asyncio.Event,
        lease_lost: asyncio.Event,
    ) -> None:
        """Keep the lease alive during extraction and retry backoff."""
        while True:
            try:
                await asyncio.wait_for(
                    stop_event.wait(),
                    timeout=LEASE_RENEW_INTERVAL,
                )
                return
            except asyncio.TimeoutError:
                pass

            try:
                renewed = await asyncio.to_thread(
                    self.renew_lease,
                    document_id,
                    token,
                )
            except Exception:
                logger.exception(
                    "Could not renew lease for document %s",
                    document_id,
                )
                lease_lost.set()
                return

            if not renewed:
                logger.warning(
                    "Lease lost for document %s",
                    document_id,
                )
                lease_lost.set()
                return


    async def process_document(
        self,
        document_id: UUID,
        token: UUID,
    ) -> None:
        stop_event = asyncio.Event()
        lease_lost = asyncio.Event()

        heartbeat_task = asyncio.create_task(
            self._heartbeat(
                document_id,
                token,
                stop_event,
                lease_lost,
            )
        )

        partial_data = {}

        try:
            while True:
                if lease_lost.is_set():
                    return

                with SessionLocal() as session:
                    document = session.get(Document, document_id)

                    if document is None:
                        return

                    if (
                        document.status != DocumentStatus.PROCESSING
                        or document.lease_token != token
                    ):
                        return

                    lease_expires_at = document.lease_expires_at

                    if lease_expires_at is None:
                        return

                    if lease_expires_at.tzinfo is None:
                        lease_expires_at = lease_expires_at.replace(
                            tzinfo=timezone.utc
                        )

                    if lease_expires_at <= utc_now():
                        return

                    content = document.content
                    attempt = document.attempt_count

                    # Existing values can come from previous attempts.
                    for field in EXTRACTED_FIELDS:
                        value = getattr(document, field)
                        if value is not None:
                            partial_data[field] = value

                try:
                    extracted = await self.extractor.extract(content)

                except PermanentExtractionError as exc:
                    # Missing or invalid total must never be retried.
                    self._mark_error(
                        document_id,
                        token,
                        str(exc),
                    )
                    return

                except TransientExtractionError as exc:
                    if lease_lost.is_set():
                        return

                    # Merge any newly extracted partial fields.
                    exc_partial = getattr(exc, "partial_data", None)
                    if exc_partial is not None:
                        for field in EXTRACTED_FIELDS:
                            value = getattr(exc_partial, field, None)
                            if value is not None:
                                partial_data[field] = value

                    if attempt >= MAX_ATTEMPTS:
                        self._mark_error(
                            document_id,
                            token,
                            str(exc),
                            partial_data,
                        )
                        return

                    if not self._save_error(
                        document_id,
                        token,
                        str(exc),
                        partial_data,
                    ):
                        return

                    # Exponential backoff: 1 second, then 2 seconds.
                    await asyncio.sleep(
                        BACKOFF_BASE * (2 ** (attempt - 1))
                    )

                    if lease_lost.is_set():
                        return

                    # Count the next attempt only if the lease is valid.
                    now = utc_now()

                    with SessionLocal.begin() as session:
                        result = session.execute(
                            update(Document)
                            .where(
                                Document.id == document_id,
                                Document.status == DocumentStatus.PROCESSING,
                                Document.lease_token == token,
                                Document.lease_expires_at > now,
                            )
                            .values(
                                attempt_count=Document.attempt_count + 1
                            )
                        )

                    if result.rowcount != 1:
                        return

                    continue

                except asyncio.CancelledError:
                    raise

                except Exception as exc:
                    logger.exception(
                        "Unexpected extraction error for document %s",
                        document_id,
                    )
                    self._mark_error(
                        document_id,
                        token,
                        f"Unexpected extraction error: {exc}",
                        partial_data,
                    )
                    return

                if lease_lost.is_set():
                    return

                # Merge successfully extracted fields with previous partials.
                for field in EXTRACTED_FIELDS:
                    value = getattr(extracted, field, None)
                    if value is not None:
                        partial_data[field] = value

                # Only the current lease owner can complete the document.
                now = utc_now()

                with SessionLocal.begin() as session:
                    result = session.execute(
                        update(Document)
                        .where(
                            Document.id == document_id,
                            Document.status == DocumentStatus.PROCESSING,
                            Document.lease_token == token,
                            Document.lease_expires_at > now,
                        )
                        .values(
                            **partial_data,
                            status=DocumentStatus.COMPLETED,
                            last_error=None,
                            processed_at=now,
                            lease_token=None,
                            lease_expires_at=None,
                        )
                    )

                if result.rowcount == 1:
                    logger.info(
                        "Document %s completed",
                        document_id,
                    )
                else:
                    logger.warning(
                        "Document %s was not completed: lease lost",
                        document_id,
                    )

                return

        finally:
            stop_event.set()
            await heartbeat_task

    def _save_error(
        self,
        document_id: UUID,
        token: UUID,
        message: str,
        partial_data: dict | None = None,
    ) -> bool:
        """Save retry state and available fields while the lease is valid."""
        now = utc_now()

        values = {"last_error": message}

        if partial_data:
            values.update({
                field: value
                for field, value in partial_data.items()
                if field in EXTRACTED_FIELDS and value is not None
            })

        with SessionLocal.begin() as session:
            result = session.execute(
                update(Document)
                .where(
                    Document.id == document_id,
                    Document.status == DocumentStatus.PROCESSING,
                    Document.lease_token == token,
                    Document.lease_expires_at > now,
                )
                .values(**values)
            )

            return result.rowcount == 1

    def _mark_error(
        self,
        document_id: UUID,
        token: UUID,
        message: str,
        partial_data: dict | None = None,
    ) -> None:
        """Mark a document as failed and persist any available fields."""
        now = utc_now()

        values = {
            "status": DocumentStatus.ERROR,
            "last_error": message,
            "processed_at": now,
            "lease_token": None,
            "lease_expires_at": None,
        }

        if partial_data:
            values.update({
                field: value
                for field, value in partial_data.items()
                if field in EXTRACTED_FIELDS and value is not None
            })

        with SessionLocal.begin() as session:
            result = session.execute(
                update(Document)
                .where(
                    Document.id == document_id,
                    Document.status == DocumentStatus.PROCESSING,
                    Document.lease_token == token,
                    Document.lease_expires_at > now,
                )
                .values(**values)
            )

            if result.rowcount == 1:
                logger.error(
                    "Document %s failed: %s",
                    document_id,
                    message,
                )

    async def run(self) -> None:
        logger.info("Document worker started")

        while True:
            try:
                self.recover_stale_documents()
                claimed = self.claim_next_document()

                if claimed is None:
                    await asyncio.sleep(POLL_INTERVAL)
                    continue

                document_id, token = claimed
                await self.process_document(document_id, token)

            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Unexpected error in document worker")
                await asyncio.sleep(POLL_INTERVAL)