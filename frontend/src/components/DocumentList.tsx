import { useCallback, useEffect, useRef, useState, type FormEvent, } from "react";

import { getDocuments, retryDocument, } from "../api/documents";

import type { DocumentItem, DocumentStatus, } from "../types/document";

const PAGE_SIZE = 10;

const statuses: DocumentStatus[] = [
    "pending",
    "processing",
    "completed",
    "error",
    "reviewed",
];

const statusLabels: Record<DocumentStatus, string> = {
    pending: "Pending",
    processing: "Processing",
    completed: "Completed",
    error: "Error",
    reviewed: "Reviewed",
};

interface DocumentListProps {
    refreshKey: number;
}

function formatDate(value: string | null): string {
    if (!value) return "—";

    // Treat YYYY-MM-DD as a calendar date, not a UTC timestamp.
    const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);

    if (match) {
        return new Date(
            Number(match[1]),
            Number(match[2]) - 1,
            Number(match[3])
        ).toLocaleDateString();
    }

    const date = new Date(value);

    return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString();
}

function formatAmount(amount: number | null, currency: string | null): string {

    if (amount === null) return "—";

    try {
        if (currency) {
            return new Intl.NumberFormat(undefined, {
                style: "currency",
                currency,
            }).format(amount);
        }

        return new Intl.NumberFormat().format(amount);
    } catch {
        return `${amount} ${currency ?? ""}`.trim();
    }
}

export default function DocumentList({
    refreshKey,
}: DocumentListProps) {
    const [documents, setDocuments] = useState<DocumentItem[]>([]);
    const [total, setTotal] = useState(0);

    const [page, setPage] = useState(1);

    const [status, setStatus] = useState<DocumentStatus | "">("");
    const [supplierInput, setSupplierInput] = useState("");
    const [supplierFilter, setSupplierFilter] = useState("");

    const [filtersOpen, setFiltersOpen] = useState(false);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");
    const [retryingId, setRetryingId] = useState<string | null>(null);

    const loadDocuments = useCallback(async () => {
        setLoading(true);
        setError("");

        try {
            const result = await getDocuments({
                page,
                page_size: PAGE_SIZE,
                status: status || undefined,
                supplier: supplierFilter || undefined,
            });

            setDocuments(result.items);
            setTotal(result.total);
        } catch (err) {
            setError(
                err instanceof Error
                    ? err.message
                    : "Could not load documents."
            );
        } finally {
            setLoading(false);
        }
    }, [page, status, supplierFilter, refreshKey]);

    useEffect(() => {
        void loadDocuments();
    }, [loadDocuments]);

    const hasProcessingDocuments = documents.some(
        (doc) => doc.status === "pending" || doc.status === "processing"
    );

    const loadDocumentsRef = useRef(loadDocuments);

    useEffect(() => {
        loadDocumentsRef.current = loadDocuments;
    }, [loadDocuments]);

    useEffect(() => {
        if (!hasProcessingDocuments) return;

        const intervalId = window.setInterval(() => {
            void loadDocumentsRef.current();
        }, 3000);

        return () => window.clearInterval(intervalId);
    }, [hasProcessingDocuments]);

    const totalPages = Math.ceil(total / PAGE_SIZE);

    function applyFilters(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();

        const formData = new FormData(event.currentTarget);
        const selectedStatus = String(formData.get("status") ?? "");
        const selectedSupplier = String(
            formData.get("supplier") ?? ""
        ).trim();

        setPage(1);
        setStatus(selectedStatus as DocumentStatus | "");
        setSupplierInput(selectedSupplier);
        setSupplierFilter(selectedSupplier);
        setFiltersOpen(false);
    }

    function clearFilters() {
        setStatus("");
        setSupplierInput("");
        setSupplierFilter("");
        setPage(1);
        setFiltersOpen(false);
    }

    async function handleRetry(id: string) {
        setRetryingId(id);
        setError("");

        try {
            await retryDocument(id);
            await loadDocuments();
        } catch (err) {
            setError(
                err instanceof Error
                    ? err.message
                    : "Could not retry the document."
            );
        } finally {
            setRetryingId(null);
        }
    }

    return (
        <section className="panel document-list">
            <div className="section-heading list-heading">
                <div>
                    <h2>Documents</h2>
                    <p>
                        Browse, filter, and monitor uploaded documents.
                    </p>
                </div>

                <button
                    type="button"
                    className="button button-secondary"
                    aria-expanded={filtersOpen}
                    onClick={() => setFiltersOpen((open) => !open)}
                >
                    <svg
                        width="16"
                        height="16"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="1.8"
                        strokeLinecap="round"
                    >
                        <path d="M4 7h16M7 12h10m-7 5h4" />
                    </svg>

                    Filters

                    {(status || supplierFilter) && (
                        <span
                            className="filter-dot"
                            aria-label="Filters active"
                        />
                    )}
                </button>
            </div>

            {filtersOpen && (
                <form
                    className="filter-form"
                    onSubmit={applyFilters}
                >
                    <div className="filter-grid">
                        <label>
                            Status

                            <select name="status" defaultValue={status}>
                                <option value="">All statuses</option>

                                {statuses.map((item) => (
                                    <option key={item} value={item}>
                                        {statusLabels[item]}
                                    </option>
                                ))}
                            </select>
                        </label>

                        <label>
                            Supplier

                            <input
                                type="text"
                                name="supplier"
                                value={supplierInput}
                                onChange={(event) =>
                                    setSupplierInput(event.target.value)
                                }
                                placeholder="Enter supplier name"
                                maxLength={255}
                            />
                        </label>
                    </div>

                    <div className="filter-actions">
                        <button
                            type="button"
                            className="button button-secondary"
                            onClick={clearFilters}
                        >
                            Clear filters
                        </button>

                        <button
                            type="submit"
                            className="button button-primary"
                        >
                            Apply filters
                        </button>
                    </div>
                </form>
            )}

            <div className="list-summary">
                <span>
                    {total} document{total === 1 ? "" : "s"}
                </span>

                {(status || supplierFilter) && (
                    <button
                        type="button"
                        className="text-button"
                        onClick={clearFilters}
                    >
                        Clear active filters
                    </button>
                )}
            </div>

            {error && (
                <p className="feedback error" role="alert">
                    {error}
                </p>
            )}

            <div className="table-wrapper">
                <table>
                    <thead>
                        <tr>
                            <th>Filename</th>
                            <th>Supplier</th>
                            <th>Invoice date</th>
                            <th>Total amount</th>
                            <th>Status</th>
                            <th>Actions</th>
                        </tr>
                    </thead>

                    <tbody>
                        {loading ? (
                            <tr>
                                <td colSpan={6} className="empty-state">
                                    Loading documents...
                                </td>
                            </tr>
                        ) : documents.length === 0 ? (
                            <tr>
                                <td colSpan={6} className="empty-state">
                                    No documents found.
                                    <br />
                                    Try changing your filters or uploading a document.
                                </td>
                            </tr>
                        ) : (
                            documents.map((doc) => (
                                <tr key={doc.id}>
                                    <td>
                                        <div className="filename-cell">
                                            <span className="file-icon">TXT</span>
                                            <span
                                                className="filename-text"
                                                title={doc.filename}
                                            >
                                                {doc.filename}
                                            </span>
                                        </div>
                                    </td>

                                    <td>{doc.supplier || "—"}</td>

                                    <td>{formatDate(doc.invoice_date)}</td>

                                    <td>
                                        {formatAmount(
                                            doc.total_amount,
                                            doc.currency
                                        )}
                                    </td>

                                    <td>
                                        <span
                                            className={`status status-${doc.status}`}
                                        >
                                            <span className="status-dot" />
                                            {statusLabels[doc.status]}
                                        </span>
                                    </td>

                                    <td>
                                        {doc.status === "error" ? (
                                            <button
                                                type="button"
                                                className="text-button"
                                                disabled={retryingId === doc.id}
                                                onClick={() => void handleRetry(doc.id)}
                                            >
                                                {retryingId === doc.id
                                                    ? "Retrying..."
                                                    : "Retry"}
                                            </button>
                                        ) : (
                                            <span className="muted">—</span>
                                        )}
                                    </td>
                                </tr>
                            ))
                        )}
                    </tbody>
                </table>
            </div>

            <div className="pagination">
                <span>
                    {total === 0
                        ? "Showing 0 documents"
                        : `Showing ${(page - 1) * PAGE_SIZE + 1}–${Math.min(
                            page * PAGE_SIZE,
                            total
                        )} of ${total}`}
                </span>

                <div className="pagination-controls">
                    <button
                        type="button"
                        className="page-button"
                        disabled={page <= 1 || loading}
                        aria-label="Previous page"
                        onClick={() => setPage((current) => current - 1)}
                    >
                        ‹
                    </button>

                    <span className="page-number">
                        {page} / {Math.max(1, totalPages)}
                    </span>

                    <button
                        type="button"
                        className="page-button"
                        disabled={
                            loading ||
                            totalPages === 0 ||
                            page >= totalPages
                        }
                        aria-label="Next page"
                        onClick={() => setPage((current) => current + 1)}
                    >
                        ›
                    </button>
                </div>
            </div>
        </section>
    );
}