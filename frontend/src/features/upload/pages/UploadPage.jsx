import { useState } from "react";
import { useNavigate } from "react-router-dom";
import FileUpload from "../components/FileUpload/FileUpload";
import { useUpload } from "../hooks/useUpload";
import "./UploadPage.css";

function UploadPage() {
    const navigate = useNavigate();

    const [currency, setCurrency] = useState("");
    const {
        selectedFile,
        isUploading,
        uploadResult,
        uploadError,
        handleFileSelect,
        handleUpload,
    } = useUpload();

    // Step 1 of the upload workflow. Every file we managed to read continues to
    // the column-mapping review (step 2), so the user always confirms what each
    // column was understood as before the rows are used. Mapping used to be
    // offered only when the automatic matcher failed outright, which meant a
    // file whose columns happened to match never showed the step at all.
    //
    // The currency is the user's choice for this upload - it's sent to the
    // backend (see useUpload.js) and stored with the dataset itself, so
    // switching between files later always shows each one in the currency
    // it was actually uploaded with. It's also forwarded via route state to
    // the mapping review screen, since that screen is what actually
    // finishes the upload when the automatic column match needed manual
    // correction (see MappingReviewPage / useMapping.js).
    const handleUploadAndContinue = async () => {
        const result = await handleUpload(currency);

        if (result?.columns?.length > 0) {
            navigate("/mapping", {
                state: {
                    filename: result.filename,
                    dataType: result.data_type,
                    columns: result.columns,
                    currency,
                },
            });
        }
    };

    return (
        <div className="page-shell">
            <div className="page-content">
                <div className="content-card upload-hero">
                    <div className="upload-hero-icon">↑</div>

                    <h2 className="upload-hero-title">
                        Let's start with your sales history
                    </h2>

                    <p className="upload-hero-subtitle">
                        Upload one Excel or CSV export and this page fills itself in.
                        Three months is enough to begin; twelve or more makes the
                        forecast much tighter.
                    </p>

                    <FileUpload
                        onFileSelect={handleFileSelect}
                        currency={currency}
                        onCurrencyChange={setCurrency}
                    />

                    <div className="upload-button-wrap">
                        <button
                            onClick={handleUploadAndContinue}
                            disabled={!selectedFile || !currency || isUploading}
                            className="upload-button upload-button-large"
                        >
                            {isUploading
                                ? "Uploading..."
                                : !currency
                                  ? "Select a currency first"
                                  : "Upload File"}
                        </button>
                    </div>

                    {uploadResult && (
                        <div
                            className={`status-box ${uploadResult.stored ? "status-success" : "status-error"}`}
                        >
                            <p>
                                {uploadResult.stored ? "✅" : "⚠️"}{" "}
                                {uploadResult.message}
                            </p>
                            <p>Filename: {uploadResult.filename}</p>
                            <p>Size: {uploadResult.size_kb} KB</p>
                            <p>Extension: {uploadResult.extension}</p>
                        </div>
                    )}

                    {uploadError && (
                        <div className="status-box status-error">
                            <p>❌ {uploadError}</p>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}

export default UploadPage;
