from uuid import UUID

from fastapi import APIRouter, File, HTTPException, UploadFile, status, Query
from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.models.document import Document, DocumentStatus
from app.schemas.document import (DocumentCorrection,DocumentDetailResponse,DocumentListItem,DocumentListResponse,DocumentStatusResponse,UploadResponse,UploadedDocument)

router = APIRouter(prefix="/documents", tags=["documents"])

MAX_FILE_SIZE = 1_048_576  # 1 MB


@router.post(
    "",
    response_model=UploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_documents(
    files: list[UploadFile] = File(...),
) -> UploadResponse:
    if not files:
        raise HTTPException(
            status_code=400,
            detail="Debes subir al menos un fichero.",
        )

    # Validate every file before inserting any documents.
    validated_files: list[tuple[str, str]] = []

    for file in files:
        filename = file.filename or ""

        if not filename.lower().endswith(".txt"):
            raise HTTPException(
                status_code=400,
                detail=f"Solo se aceptan ficheros .txt: {filename}",
            )

        content_bytes = await file.read(MAX_FILE_SIZE + 1)

        if len(content_bytes) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"El fichero supera el límite de 1 MB: {filename}",
            )

        try:
            content = content_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise HTTPException(
                status_code=400,
                detail=f"El fichero no contiene texto UTF-8 válido: {filename}",
            ) from exc

        validated_files.append((filename, content))

    created: list[UploadedDocument] = []

    with SessionLocal.begin() as session:
        for filename, content in validated_files:
            document = Document(
                filename=filename,
                content=content,
                status=DocumentStatus.PENDING,
            )
            session.add(document)
            session.flush()

            created.append(
                UploadedDocument(
                    id=document.id,
                    filename=document.filename,
                    status=document.status,
                )
            )

    return UploadResponse(documents=created)


@router.post(
    "/{document_id}/retry",
    response_model=UploadedDocument,
    status_code=status.HTTP_200_OK,
)
def retry_document(document_id: UUID) -> UploadedDocument:
    with SessionLocal.begin() as session:
        document = session.scalar(
            select(Document)
            .where(Document.id == document_id)
            .with_for_update()
        )

        if document is None:
            raise HTTPException(
                status_code=404,
                detail="Documento no encontrado.",
            )

        if document.status != DocumentStatus.ERROR:
            raise HTTPException(
                status_code=409,
                detail="Solo se pueden reintentar documentos en estado error.",
            )

        document.status = DocumentStatus.PENDING
        document.attempt_count = 0
        document.last_error = None
        document.processed_at = None
        document.lease_token = None
        document.lease_expires_at = None

        result = UploadedDocument(
            id=document.id,
            filename=document.filename,
            status=document.status,
        )

    return result


@router.get(
    "/{document_id}",
    response_model=DocumentDetailResponse,
)
def get_document(document_id: UUID) -> DocumentDetailResponse:
    with SessionLocal() as session:
        document = session.get(Document, document_id)

        if document is None:
            raise HTTPException(
                status_code=404,
                detail="Documento no encontrado.",
            )

        return DocumentDetailResponse(
            id=document.id,
            filename=document.filename,
            status=document.status,
            supplier=document.supplier,
            invoice_date=(
                document.invoice_date.isoformat()
                if document.invoice_date
                else None
            ),
            total_amount=(
                float(document.total_amount)
                if document.total_amount is not None
                else None
            ),
            currency=document.currency,
            attempt_count=document.attempt_count,
            last_error=document.last_error,
            content=document.content,
            created_at=document.created_at,
        )


@router.get("", response_model=DocumentListResponse)
def list_documents(
    document_status: DocumentStatus | None = Query(
        default=None,
        alias="status",
    ),
    supplier: str | None = Query(default=None, min_length=1),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> DocumentListResponse:
    with SessionLocal() as session:
        query = select(Document)

        if document_status is not None:
            query = query.where(Document.status == document_status)

        if supplier:
            query = query.where(
                Document.supplier.ilike(f"%{supplier.strip()}%")
            )

        total = session.scalar(
            select(func.count()).select_from(query.subquery())
        ) or 0

        documents = session.scalars(
            query
            .order_by(Document.created_at.desc(), Document.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()

        return DocumentListResponse(
            items=[
                DocumentListItem(
                    id=doc.id,
                    filename=doc.filename,
                    status=doc.status,
                    supplier=doc.supplier,
                    invoice_date=(
                        doc.invoice_date.isoformat()
                        if doc.invoice_date
                        else None
                    ),
                    total_amount=(
                        float(doc.total_amount)
                        if doc.total_amount is not None
                        else None
                    ),
                    currency=doc.currency,
                    attempt_count=doc.attempt_count,
                    last_error=doc.last_error,
                    created_at=doc.created_at,
                )
                for doc in documents
            ],
            total=total,
            page=page,
            page_size=page_size,
        )
        

@router.patch(
    "/{document_id}",
    response_model=DocumentDetailResponse,
)
def update_document(
    document_id: UUID,
    payload: DocumentCorrection,
) -> DocumentDetailResponse:
    changes = payload.model_dump(exclude_unset=True,)

    with SessionLocal.begin() as session:
        document = session.scalar(
            select(Document)
            .where(Document.id == document_id)
            .with_for_update()
        )

        if document is None:
            raise HTTPException(
                status_code=404,
                detail="Documento no encontrado.",
            )

        if document.status in {
            DocumentStatus.PENDING,
            DocumentStatus.PROCESSING,
        }:
            raise HTTPException(
                status_code=409,
                detail="No se puede editar un documento pendiente o en proceso.",
            )

        for field, value in changes.items():
            setattr(document, field, value)

        document.status = DocumentStatus.REVIEWED

        result = DocumentDetailResponse(
            id=document.id,
            filename=document.filename,
            status=document.status,
            supplier=document.supplier,
            invoice_date=document.invoice_date,
            total_amount=document.total_amount,
            currency=document.currency,
            attempt_count=document.attempt_count,
            last_error=document.last_error,
            content=document.content,
            created_at=document.created_at,
        )

    return result