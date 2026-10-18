import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { getDocument, updateDocument } from "../api/documents";
import type { DocumentDetail } from "../types/document";

import DocumentEditForm, { type DocumentCorrectionPayload, } from "../components/DocumentEditForm";

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

    const [editing, setEditing] = useState(false);
    const [saving, setSaving] = useState(false);
    const [saveError, setSaveError] = useState("");

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

    async function handleSaveCorrections(payload: DocumentCorrectionPayload) {
        if (!id) {
            throw new Error("Document ID is missing.");
        }

        setSaving(true);
        setSaveError("");

        try {
            const updatedDocument = await updateDocument(id, payload);

            setDocument(updatedDocument);
            setEditing(false);
        } catch (err) {
            const message =
                err instanceof Error
                    ? err.message
                    : "Could not save document corrections.";

            setSaveError(message);
            throw err;
        } finally {
            setSaving(false);
        }
    }

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

                        {editing && (
                            <DocumentEditForm
                                document={document}
                                saving={saving}
                                onSave={handleSaveCorrections}
                                onCancel={() => setEditing(false)}
                            />
                        )}
                        <section className="panel details-panel">
                            <div className="details-heading">
                                <div>
                                    <span className="eyebrow">
                                        FILE INFORMATION
                                    </span>
                                    <h2>{document.filename}</h2>
                                </div>

                                <div className="details-heading-actions">
                                    <span className={`status status-${document.status}`}>
                                        <span className="status-dot" />
                                        {statusLabels[document.status]}
                                    </span>

                                    {saveError && !editing && (
                                        <p className="feedback error" role="alert">
                                            {saveError}
                                        </p>
                                    )}

                                    <button
                                        type="button"
                                        className="edit-icon-button"
                                        aria-label="Edit document details"
                                        title="Edit document details"
                                        disabled={
                                            editing ||
                                            document.status === "pending" ||
                                            document.status === "processing"
                                        }
                                        onClick={() => {
                                            setSaveError("");
                                            setEditing(true);
                                        }}
                                    >
                                        <svg
                                            width="18"
                                            height="18"
                                            viewBox="0 0 24 24"
                                            fill="none"
                                            stroke="currentColor"
                                            strokeWidth="2"
                                            strokeLinecap="round"
                                            strokeLinejoin="round"
                                            aria-hidden="true"
                                        >
                                            <path d="M12 20h9" />
                                            <path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L8 18l-4 1 1-4Z" />
                                        </svg>
                                    </button>
                                </div>
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