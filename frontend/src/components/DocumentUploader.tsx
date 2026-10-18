import { useRef, useState } from "react";
import { uploadDocuments } from "../api/documents";
import "../styles/DocumentUploader.css";

interface DocumentUploaderProps {
    onUploaded: () => void;
}

const MAX_FILE_SIZE = 1_048_576;

export default function DocumentUploader({ onUploaded, }: DocumentUploaderProps) {
    const inputRef = useRef<HTMLInputElement>(null);

    const [files, setFiles] = useState<File[]>([]);
    const [error, setError] = useState("");
    const [message, setMessage] = useState("");
    const [loading, setLoading] = useState(false);

    function selectFiles(fileList: FileList | null) {
        if (!fileList) return;

        const incoming = Array.from(fileList);

        const invalidFile = incoming.find(
            (file) =>
                !file.name.toLowerCase().endsWith(".txt") ||
                file.size > MAX_FILE_SIZE
        );

        if (invalidFile) {
            setError(
                !invalidFile.name.toLowerCase().endsWith(".txt")
                    ? `${invalidFile.name}: only .txt files are accepted.`
                    : `${invalidFile.name}: the maximum size is 1 MB.`
            );
            return;
        }

        setError("");
        setMessage("");

        setFiles((previous) => {
            const combined = [...previous];

            for (const file of incoming) {
                const alreadySelected = combined.some(
                    (existing) =>
                        existing.name === file.name &&
                        existing.size === file.size &&
                        existing.lastModified === file.lastModified
                );

                if (!alreadySelected) {
                    combined.push(file);
                }
            }

            return combined;
        });
    }

    function removeFile(index: number) {
        setFiles((previous) =>
            previous.filter((_, fileIndex) => fileIndex !== index)
        );

        setError("");
        setMessage("");
    }

    async function handleUpload() {
        if (files.length === 0 || loading) return;

        setLoading(true);
        setError("");
        setMessage("");

        try {
            const result = await uploadDocuments(files);

            setMessage(
                `${result.documents.length} document(s) accepted successfully.`
            );

            setFiles([]);

            if (inputRef.current) {
                inputRef.current.value = "";
            }

            onUploaded();
        } catch (err) {
            setError(
                err instanceof Error
                    ? err.message
                    : "An unexpected upload error occurred."
            );
        } finally {
            setLoading(false);
        }
    }

    return (
        <section className="uploader-panel panel">
            <div className="uploader-heading section-heading">
                <div>
                    <h2>Upload documents</h2>
                    <p>
                        Select one or more text files to upload for processing.
                    </p>
                </div>
            </div>

            <div
                className="drop-zone"
                onDragOver={(event) => event.preventDefault()}
                onDrop={(event) => {
                    event.preventDefault();
                    selectFiles(event.dataTransfer.files);
                }}
            >
                <div className="upload-icon" aria-hidden="true">
                    <svg
                        width="28"
                        height="28"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="1.8"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                    >
                        <path d="M12 16V4" />
                        <path d="m7 9 5-5 5 5" />
                        <path d="M20 16.5v2A1.5 1.5 0 0 1 18.5 20h-13A1.5 1.5 0 0 1 4 18.5v-2" />
                    </svg>
                </div>

                <h3>Drop your files here</h3>
                <p>Or browse your computer to select files.</p>
                <p className="file-hint">
                    .txt files only · Maximum 1 MB per file
                </p>

                <button
                    type="button"
                    className="button button-secondary"
                    disabled={loading}
                    onClick={() => inputRef.current?.click()}
                >
                    Browse files
                </button>

                <input
                    ref={inputRef}
                    type="file"
                    accept=".txt,text/plain"
                    multiple
                    hidden
                    onChange={(event) => {
                        selectFiles(event.target.files);
                        event.target.value = "";
                    }}
                />
            </div>

            {files.length > 0 && (
                <div className="selected-files">
                    <div className="selected-files-heading">
                        <strong>Selected files ({files.length})</strong>

                        <button
                            type="button"
                            className="text-button"
                            disabled={loading}
                            onClick={() => {
                                setFiles([]);
                                setError("");
                                setMessage("");

                                if (inputRef.current) {
                                    inputRef.current.value = "";
                                }
                            }}
                        >
                            Clear all
                        </button>
                    </div>

                    {files.map((file, index) => (
                        <div
                            className="selected-file"
                            key={`${file.name}-${file.size}-${file.lastModified}-${index}`}
                        >
                            <span className="file-icon">TXT</span>

                            <span className="file-name" title={file.name}>
                                {file.name}
                            </span>

                            <span className="file-size">
                                {(file.size / 1024).toFixed(1)} KB
                            </span>

                            <button
                                type="button"
                                className="remove-file"
                                aria-label={`Remove ${file.name}`}
                                disabled={loading}
                                onClick={() => removeFile(index)}
                            >
                                ×
                            </button>
                        </div>
                    ))}
                </div>
            )}

            {error && (
                <p className="feedback error" role="alert">
                    {error}
                </p>
            )}

            {message && (
                <p className="feedback success" role="status">
                    {message}
                </p>
            )}

            <div className="upload-actions">
                <button
                    type="button"
                    className="button button-primary"
                    disabled={files.length === 0 || loading}
                    onClick={() => void handleUpload()}
                >
                    {loading
                        ? "Uploading..."
                        : `Upload ${files.length} file${files.length === 1 ? "" : "s"}`}
                </button>
            </div>
        </section>
    );
}