from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.document import DocumentStatus


class UploadedDocument(BaseModel):
    id: UUID
    filename: str
    status: DocumentStatus


class UploadResponse(BaseModel):
    documents: list[UploadedDocument]


class DocumentStatusResponse(UploadedDocument):
    supplier: str | None
    invoice_date: date | None
    total_amount: Decimal | None
    currency: str | None
    attempt_count: int
    last_error: str | None


class DocumentListItem(DocumentStatusResponse):
    created_at: datetime


class DocumentListResponse(BaseModel):
    items: list[DocumentListItem]
    total: int
    page: int
    page_size: int


class DocumentDetailResponse(DocumentStatusResponse):
    content: str
    created_at: datetime


class DocumentCorrection(BaseModel):
    supplier: str | None = Field(default=None, max_length=255)
    invoice_date: date | None = None
    total_amount: Decimal | None = Field(default=None, ge=0)
    currency: str | None = Field(
        default=None,
        min_length=3,
        max_length=3,
        pattern=r"^[A-Za-z]{3}$",
    )