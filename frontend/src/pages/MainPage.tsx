
import { useState } from "react";

import DocumentUploader from "../components/DocumentUploader";
import DocumentList from "../components/DocumentList";

import "./MainPage.css";

export default function MainPage() {
    const [refreshKey, setRefreshKey] = useState(0);

    function refreshDocuments() {
        setRefreshKey((current) => current + 1);
    }

    return (
        <main className="app">
            <header className="topbar">
                <a className="brand" href="/" aria-label="BillManager home">
                    <span className="brand-icon">BM</span>
                    <span>BillManager</span>
                </a>
            </header>

            <div className="dashboard">
                <div className="page-intro">
                    <span className="eyebrow">WORKSPACE</span>

                    <h1>Bill management</h1>

                    <p>
                        Upload your documents and track their processing status.
                    </p>
                </div>

                <DocumentUploader onUploaded={refreshDocuments} />

                <DocumentList refreshKey={refreshKey} />
            </div>
        </main>
    );
}