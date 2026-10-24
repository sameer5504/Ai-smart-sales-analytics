import { authFetch } from "../../../shared/utils/authFetch";

const API_BASE_URL = import.meta.env.VITE_API_URL;

export async function uploadFile(file, dataType = "sales", currency) {
    const formData = new FormData();

    formData.append("file", file);
    formData.append("data_type", dataType);
    formData.append("currency", currency);

    const response = await authFetch(`${API_BASE_URL}/api/upload`, {
        method: "POST",
        body: formData,
    });

    const data = await response.json();

    if (!response.ok) {
        const message = Array.isArray(data.detail)
            ? data.detail.map((error) => error.msg).join(", ")
            : data.detail || "An error occurred while uploading the file";

        throw new Error(message);
    }

    return data;
}
