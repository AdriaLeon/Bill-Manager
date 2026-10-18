import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models.document import Document, DocumentStatus
from app.services.exceptions import (
    TransientExtractionError,
)
from app.services.extractor import InvoiceExtractor
import app.services.document_worker as worker_module


SAMPLES_DIR = Path(__file__).parent / "samples"


def load_sample(filename: str) -> str:
    path = SAMPLES_DIR / filename
    return path.read_text(encoding="utf-8")


@pytest.fixture
def db(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(
        bind=engine,
        autoflush=False,
        expire_on_commit=False,
    )

    Base.metadata.create_all(bind=engine)
    monkeypatch.setattr(
        worker_module, "SessionLocal", TestingSessionLocal
    )

    yield TestingSessionLocal

    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def fast_retries(monkeypatch):
    monkeypatch.setattr(worker_module, "BACKOFF_BASE", 0)
    monkeypatch.setattr(
        worker_module, "LEASE_RENEW_INTERVAL", 3600
    )


def create_processing_document(db, content, filename):
    token = uuid4()

    with db.begin() as session:
        document = Document(
            filename=filename,
            content=content,
            status=DocumentStatus.PROCESSING,
            attempt_count=1,
            lease_token=token,
            lease_expires_at=(
                worker_module.utc_now() + timedelta(minutes=5)
            ),
        )
        session.add(document)
        session.flush()
        document_id = document.id

    return document_id, token


class AlwaysTransientExtractor:
    def __init__(self):
        self.calls = 0

    async def extract(self, content):
        self.calls += 1
        raise TransientExtractionError(
            "Temporary service error"
        )


@pytest.mark.asyncio
async def test_worker_retries_transient_errors_three_times(
    db, fast_retries
):
    extractor = AlwaysTransientExtractor()
    worker = worker_module.DocumentWorker(extractor=extractor)

    filename = "invoice_no_supplier.txt"
    content = load_sample(filename)

    document_id, token = create_processing_document(
        db, content, filename
    )

    await worker.process_document(document_id, token)

    with db() as session:
        document = session.get(Document, document_id)

        assert document.status == DocumentStatus.ERROR
        assert document.attempt_count == 3
        assert document.last_error == "Temporary service error"
        assert document.processed_at is not None
        assert document.lease_token is None
        assert document.lease_expires_at is None

    assert extractor.calls == 3


@pytest.mark.asyncio
async def test_worker_marks_missing_total_as_permanent_error(
    db, fast_retries
):
    extractor = InvoiceExtractor(
        failure_rate=0,
        min_latency=0,
        max_latency=0,
    )
    worker = worker_module.DocumentWorker(extractor=extractor)

    filename = "invoice_no_total.txt"
    content = load_sample(filename)

    document_id, token = create_processing_document(
        db, content, filename
    )

    await worker.process_document(document_id, token)

    with db() as session:
        document = session.get(Document, document_id)

        assert document.status == DocumentStatus.ERROR
        assert document.attempt_count == 1
        assert "Total" in document.last_error
        assert document.processed_at is not None
        assert document.lease_token is None
        assert document.lease_expires_at is None


@pytest.mark.asyncio
async def test_worker_processes_valid_invoice(
    db, fast_retries
):
    extractor = InvoiceExtractor(
        failure_rate=0,
        min_latency=0,
        max_latency=0,
    )
    worker = worker_module.DocumentWorker(extractor=extractor)

    filename = "invoice_valid.txt"
    content = load_sample(filename)

    document_id, token = create_processing_document(
        db, content, filename
    )

    await worker.process_document(document_id, token)

    with db() as session:
        document = session.get(Document, document_id)

        assert document.status == DocumentStatus.COMPLETED
        assert document.attempt_count == 1
        assert document.processed_at is not None
        assert document.lease_token is None
        assert document.lease_expires_at is None

        assert document.supplier == "ACME S.L."
        assert str(document.invoice_date) == "2004-12-01"


def create_pending_document(db, filename: str) -> UUID:
    content = load_sample(filename)

    with db.begin() as session:
        document = Document(
            filename=filename,
            content=content,
            status=DocumentStatus.PENDING,
            attempt_count=0,
        )
        session.add(document)
        session.flush()
        document_id = document.id

    return document_id


@pytest.mark.asyncio
async def test_document_lifecycle_pending_to_completed(db, fast_retries):
    worker = worker_module.DocumentWorker(
        extractor=InvoiceExtractor(
            failure_rate=0,
            min_latency=0,
            max_latency=0,
        )
    )

    document_id = create_pending_document(
        db, "invoice_valid.txt"
    )

    # State 1: PENDING
    with db() as session:
        document = session.get(Document, document_id)
        assert document.status == DocumentStatus.PENDING
        assert document.attempt_count == 0

    # Transition: PENDING -> PROCESSING
    claimed = worker.claim_next_document()
    assert claimed is not None

    claimed_id, token = claimed
    assert claimed_id == document_id

    with db() as session:
        document = session.get(Document, document_id)
        assert document.status == DocumentStatus.PROCESSING
        assert document.attempt_count == 1
        assert document.lease_token == token
        assert document.lease_expires_at is not None

    # Transition: PROCESSING -> COMPLETED
    await worker.process_document(document_id, token)

    with db() as session:
        document = session.get(Document, document_id)
        assert document.status == DocumentStatus.COMPLETED
        assert document.processed_at is not None
        assert document.lease_token is None
        assert document.lease_expires_at is None
        assert document.supplier == "ACME S.L."


@pytest.mark.asyncio
async def test_document_lifecycle_pending_to_error(
    db, fast_retries
):
    worker = worker_module.DocumentWorker(
        extractor=InvoiceExtractor(
            failure_rate=0,
            min_latency=0,
            max_latency=0,
        )
    )

    document_id = create_pending_document(
        db, "invoice_no_total.txt"
    )

    # Transition: PENDING -> PROCESSING
    claimed = worker.claim_next_document()
    assert claimed is not None

    claimed_id, token = claimed
    assert claimed_id == document_id

    with db() as session:
        document = session.get(Document, document_id)
        assert document.status == DocumentStatus.PROCESSING
        assert document.attempt_count == 1

    # Transition: PROCESSING -> ERROR
    await worker.process_document(document_id, token)

    with db() as session:
        document = session.get(Document, document_id)
        assert document.status == DocumentStatus.ERROR
        assert document.attempt_count == 1
        assert "Total" in document.last_error
        assert document.processed_at is not None
        assert document.lease_token is None
        assert document.lease_expires_at is None


@pytest.mark.asyncio
async def test_worker_recovers_and_reclaims_job_after_crash(
    db, fast_retries
):
    worker = worker_module.DocumentWorker(
        extractor=InvoiceExtractor(
            failure_rate=0,
            min_latency=0,
            max_latency=0,
        )
    )

    document_id = create_pending_document(
        db, "invoice_valid.txt"
    )

    first_claim = worker.claim_next_document()
    assert first_claim is not None

    claimed_id, first_token = first_claim
    assert claimed_id == document_id

    with db.begin() as session:
        document = session.get(Document, document_id)
        assert document.status == DocumentStatus.PROCESSING
        assert document.attempt_count == 1

        # Simulate a worker crash: the job remains PROCESSING, but its lease expires.
        document.lease_expires_at = (
            worker_module.utc_now() - timedelta(seconds=1)
        )

    worker.recover_stale_documents()

    with db() as session:
        document = session.get(Document, document_id)

        assert document.status == DocumentStatus.PENDING
        assert document.attempt_count == 1
        assert document.lease_token is None
        assert document.lease_expires_at is None
        assert "lease expired" in document.last_error.lower()

    second_claim = worker.claim_next_document()
    assert second_claim is not None

    reclaimed_id, second_token = second_claim

    assert reclaimed_id == document_id
    assert second_token != first_token

    with db() as session:
        document = session.get(Document, document_id)

        assert document.status == DocumentStatus.PROCESSING
        assert document.attempt_count == 2
        assert document.lease_token == second_token
        assert document.lease_expires_at is not None

    await worker.process_document(document_id, second_token)

    with db() as session:
        document = session.get(Document, document_id)

        assert document.status == DocumentStatus.COMPLETED
        assert document.attempt_count == 2
        assert document.processed_at is not None
        assert document.lease_token is None
        assert document.lease_expires_at is None
        assert document.supplier == "ACME S.L."