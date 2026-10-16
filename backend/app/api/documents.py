
from uuid import UUID

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.document import Document, DocumentStatus

router = APIRouter(prefix="/documents", tags=["documents"])

MAX_FILE_SIZE = 1_048_576  # 1 MB


class UploadedDocument(BaseModel):
    id: UUID
    filename: str
    status: DocumentStatus


class UploadResponse(BaseModel):
    documents: list[UploadedDocument]


class DocumentStatusResponse(UploadedDocument):
    supplier: str | None
    invoice_date: str | None
    total_amount: float | None
    currency: str | None
    attempt_count: int
    last_error: str | None


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


@router.get(
    "/{document_id}",
    response_model=DocumentStatusResponse,
)
def get_document(document_id: UUID) -> DocumentStatusResponse:
    with SessionLocal() as session:
        document = session.execute(
            select(Document).where(Document.id == document_id)
        ).scalar_one_or_none()

        if document is None:
            raise HTTPException(
                status_code=404,
                detail="Documento no encontrado.",
            )

        return DocumentStatusResponse(
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
        )