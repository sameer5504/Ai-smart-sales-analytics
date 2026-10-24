import { useState } from "react";
import { uploadFile } from "../services/uploadService";

export function useUpload() {
    const [selectedFile, setSelectedFile] = useState(null);
    const [isUploading, setIsUploading] = useState(false);
    const [uploadResult, setUploadResult] = useState(null);
    const [uploadError, setUploadError] = useState("");

    const handleFileSelect = (file) => {
        setSelectedFile(file);
        setUploadResult(null);
        setUploadError("");
    };

    const handleUpload = async (currency) => {
        if (!selectedFile) return null;

        setIsUploading(true);
        setUploadError("");
        setUploadResult(null);

        try {
            const result = await uploadFile(selectedFile, "sales", currency);

            setUploadResult(result);

            if (result?.dataset_id) {
                sessionStorage.setItem("lastDatasetId", String(result.dataset_id));
            }

            return result;
        } catch (error) {
            setUploadError(error.message);
            return null;
        } finally {
            setIsUploading(false);
        }
    };

    return {
        selectedFile,
        isUploading,
        uploadResult,
        uploadError,
        handleFileSelect,
        handleUpload,
    };
}
