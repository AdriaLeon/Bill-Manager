import { useState, type FormEvent } from "react";
import type { DocumentDetail } from "../types/document";
import "../styles/DocumentEditForm.css";

export interface DocumentCorrectionPayload {
    supplier: string | null;
    invoice_date: string | null;
    total_amount: number | null;
    currency: string | null;
}

interface DocumentEditFormProps {
    document: DocumentDetail;
    saving: boolean;
    onSave: (payload: DocumentCorrectionPayload) => Promise<void>;
    onCancel: () => void;
}

export default function DocumentEditForm({
    document,
    saving,
    onSave,
    onCancel,
}: DocumentEditFormProps) {
    const [supplier, setSupplier] = useState(document.supplier ?? "");
    const [invoiceDate, setInvoiceDate] = useState(
        document.invoice_date?.slice(0, 10) ?? ""
    );
    const [totalAmount, setTotalAmount] = useState(
        document.total_amount === null
            ? ""
            : String(document.total_amount)
    );
    const [currency, setCurrency] = useState(document.currency ?? "");
    const [error, setError] = useState("");

    async function handleSubmit(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        setError("");

        let parsedAmount: number | null = null;

        if (totalAmount.trim() !== "") {
            parsedAmount = Number(totalAmount);

            if (!Number.isFinite(parsedAmount)) {
                setError("Enter a valid total amount.");
                return;
            }
        }

        try {
            await onSave({
                supplier: supplier.trim() || null,
                invoice_date: invoiceDate || null,
                total_amount: parsedAmount,
                currency: currency.trim().toUpperCase() || null,
            });
        } catch (err) {
            setError(
                err instanceof Error
                    ? err.message
                    : "Could not save the document corrections."
            );
        }
    }

    return (
        <section className="panel edit-form-panel">
            <div className="section-heading">
                <div>
                    <h2>Edit document details</h2>
                    <p>Correct the extracted invoice information.</p>
                </div>
            </div>

            <form className="document-edit-form" onSubmit={handleSubmit}>
                <label>
                    Supplier
                    <input
                        type="text"
                        value={supplier}
                        onChange={(event) => setSupplier(event.target.value)}
                        maxLength={255}
                        placeholder="Supplier name"
                    />
                </label>

                <label>
                    Invoice date
                    <input
                        type="date"
                        value={invoiceDate}
                        onChange={(event) => setInvoiceDate(event.target.value)}
                    />
                </label>

                <label>
                    Total amount
                    <input
                        type="number"
                        value={totalAmount}
                        onChange={(event) => setTotalAmount(event.target.value)}
                        step="any"
                        placeholder="0.00"
                    />
                </label>

                <label>
                    Currency
                    <input
                        type="text"
                        value={currency}
                        onChange={(event) => setCurrency(event.target.value)}
                        maxLength={3}
                        placeholder="EUR"
                    />
                </label>

                {error && (
                    <p className="feedback error" role="alert">
                        {error}
                    </p>
                )}

                <div className="edit-form-actions">
                    <button
                        type="button"
                        className="button button-secondary"
                        onClick={onCancel}
                        disabled={saving}
                    >
                        Cancel
                    </button>

                    <button
                        type="submit"
                        className="button button-primary"
                        disabled={saving}
                    >
                        {saving ? "Saving..." : "Save changes"}
                    </button>
                </div>
            </form>
        </section>
    );
}