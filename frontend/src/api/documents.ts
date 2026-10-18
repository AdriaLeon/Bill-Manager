import type {
    DocumentCorrection,
    DocumentDetail,
    DocumentListResponse,
    DocumentStatus,
    UploadedDocument,
    UploadResponse,
} from "../types/document";

const API_URL = (
    import.meta.env.VITE_API_URL ?? "http://localhost:8000"
).replace(/\/+$/, "");

export interface DocumentFilters {
    status?: DocumentStatus;
    supplier?: string;
    page: number;
    page_size: number;
}

async function handleResponse<T>(
    response: Response
): Promise<T> {
    if (!response.ok) {
        const body: unknown = await response.json().catch(() => null);

        let message = `Request failed (${response.status})`;

        if (body && typeof body === "object" && "detail" in body) {
            const detail = body.detail;

            if (typeof detail === "string") {
                message = detail;
            } else if (Array.isArray(detail)) {
                message = detail
                    .map((item) =>
                        typeof item === "object" &&
                            item !== null &&
                            "msg" in item
                            ? String(item.msg)
                            : String(item)
                    )
                    .join(", ");
            }
        }

        throw new Error(message);
    }

    return response.json() as Promise<T>;
}

export async function uploadDocuments(
    files: File[]
): Promise<UploadResponse> {
    const formData = new FormData();

    for (const file of files) {
        formData.append("files", file);
    }

    const response = await fetch(`${API_URL}/documents`, {
        method: "POST",
        body: formData,
    });

    return handleResponse<UploadResponse>(response);
}

export async function getDocuments(
    filters: DocumentFilters
): Promise<DocumentListResponse> {
    const params = new URLSearchParams({
        page: String(filters.page),
        page_size: String(filters.page_size),
    });

    if (filters.status) {
        params.set("status", filters.status);
    }

    if (filters.supplier?.trim()) {
        params.set("supplier", filters.supplier.trim());
    }

    const response = await fetch(
        `${API_URL}/documents?${params.toString()}`
    );

    return handleResponse<DocumentListResponse>(response);
}

export async function getDocument(
    id: string
): Promise<DocumentDetail> {
    const response = await fetch(
        `${API_URL}/documents/${encodeURIComponent(id)}`
    );

    return handleResponse<DocumentDetail>(response);
}

export async function retryDocument(
    id: string
): Promise<UploadedDocument> {
    const response = await fetch(
        `${API_URL}/documents/${encodeURIComponent(id)}/retry`,
        { method: "POST" }
    );

    return handleResponse<UploadedDocument>(response);
}

export async function updateDocument(
    id: string,
    correction: DocumentCorrection
): Promise<DocumentDetail> {
    const response = await fetch(
        `${API_URL}/documents/${encodeURIComponent(id)}`,
        {
            method: "PATCH",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify(correction),
        }
    );

    return handleResponse<DocumentDetail>(response);
}