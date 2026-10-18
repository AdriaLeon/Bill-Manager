import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { getDocument } from "../api/documents";
import type { DocumentDetail } from "../types/document";

import "./DocumentDetails.css";

const statusLabels: Record<DocumentDetail["status"], string> = {
    pending: "Pending",
    processing: "Processing",
    completed: "Completed",
    error: "Error",
    reviewed: "Reviewed",
};

function formatDate(value: string | null): string {
    if (!value) return "—";

    const date = new Date(value);

    return Number.isNaN(date.getTime())
        ? value
        : date.toLocaleString();
}

function formatAmount(amount: number | null, currency: string | null): string {
    if (amount === null) return "—";

    try {
        return currency
            ? new Intl.NumberFormat(undefined, {
                style: "currency",
                currency,
            }).format(amount)
            : String(amount);
    } catch {
        return `${amount} ${currency ?? ""}`.trim();
    }
}

export default function DocumentDetails() {
    const { id } = useParams<{ id: string }>();

    const [document, setDocument] = useState<DocumentDetail | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");

    useEffect(() => {
        let cancelled = false;

        async function loadDocument() {
            if (!id) {
                setError("Document ID is missing.");
                setLoading(false);
                return;
            }

            setLoading(true);
            setError("");

            try {
                const result = await getDocument(id);

                if (!cancelled) {
                    setDocument(result);
                }
            } catch (err) {
                if (!cancelled) {
                    setError(
                        err instanceof Error
                            ? err.message
                            : "Could not load document details."
                    );
                }
            } finally {
                if (!cancelled) {
                    setLoading(false);
                }
            }
        }

        void loadDocument();

        return () => {
            cancelled = true;
        };
    }, [id]);

    return (
        <main className="app">
            <header className="topbar">
                <Link className="brand" to="/" aria-label="BillManager home">
                    <span className="brand-icon">BM</span>
                    <span>BillManager</span>
                </Link>
            </header>

            <div className="dashboard details-dashboard">
                <Link to="/" className="back-link">
                    ← Back to documents
                </Link>

                <div className="page-intro">
                    <span className="eyebrow">DOCUMENT</span>
                    <h1>Document details</h1>
                    <p>View the document's extracted data and original content.</p>
                </div>

                {loading && (
                    <section className="panel">
                        <p>Loading document details...</p>
                    </section>
                )}

                {!loading && error && (
                    <section className="panel">
                        <p className="feedback error" role="alert">
                            {error}
                        </p>
                    </section>
                )}

                {!loading && document && (
                    <>
                        <section className="panel details-panel">
                            <div className="details-heading">
                                <div>
                                    <span className="eyebrow">
                                        FILE INFORMATION
                                    </span>
                                    <h2>{document.filename}</h2>
                                </div>

                                <span
                                    className={`status status-${document.status}`}
                                >
                                    <span className="status-dot" />
                                    {statusLabels[document.status]}
                                </span>
                            </div>

                            <dl className="details-grid">
                                <div className="detail-field detail-field-wide">
                                    <dt>Document ID</dt>
                                    <dd className="document-id">{document.id}</dd>
                                </div>

                                <div className="detail-field">
                                    <dt>Supplier</dt>
                                    <dd>{document.supplier || "—"}</dd>
                                </div>

                                <div className="detail-field">
                                    <dt>Invoice date</dt>
                                    <dd>
                                        {document.invoice_date
                                            ? formatDate(document.invoice_date)
                                            : "—"}
                                    </dd>
                                </div>

                                <div className="detail-field">
                                    <dt>Total amount</dt>
                                    <dd>
                                        {formatAmount(
                                            document.total_amount,
                                            document.currency
                                        )}
                                    </dd>
                                </div>

                                <div className="detail-field">
                                    <dt>Currency</dt>
                                    <dd>{document.currency || "—"}</dd>
                                </div>

                                <div className="detail-field">
                                    <dt>Processing attempts</dt>
                                    <dd>{document.attempt_count}</dd>
                                </div>

                                <div className="detail-field">
                                    <dt>Uploaded at</dt>
                                    <dd>{formatDate(document.created_at)}</dd>
                                </div>

                                <div className="detail-field detail-field-wide">
                                    <dt>Last processing error</dt>
                                    <dd className={document.last_error ? "error-text" : ""}>
                                        {document.last_error || "No errors"}
                                    </dd>
                                </div>
                            </dl>
                        </section>

                        <section className="panel content-panel">
                            <div className="section-heading">
                                <div>
                                    <h2>Original document content</h2>
                                    <p>Text stored when the file was uploaded.</p>
                                </div>
                            </div>

                            <pre className="document-content">
                                {document.content}
                            </pre>
                        </section>
                    </>
                )}
            </div>
        </main>
    );
}