export type DocumentStatus =
    | "PENDING"
    | "PROCESSING"
    | "ERROR"
    | "REVIEWED";

export interface DocumentItem {
    id: string;
    filename: string;
    status: DocumentStatus;
    supplier: string | null;
    invoice_date: string | null;
    total_amount: number | null;
    currency: string | null;
    attempt_count: number;
    last_error: string | null;
    created_at: string;
}

export interface UploadedDocument {
    id: string;
    filename: string;
    status: DocumentStatus;
}

export interface DocumentListResponse {
    items: DocumentItem[];
    total: number;
    page: number;
    page_size: number;
}

export interface UploadResponse {
    documents: UploadedDocument[];
}