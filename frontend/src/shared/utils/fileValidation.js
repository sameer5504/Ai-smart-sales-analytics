const ALLOWED_EXTENSIONS = ["xlsx", "xls", "csv"];
const MAX_FILE_SIZE_MB = 25;

export function getFileExtension(fileName) {
    return fileName.split(".").pop().toLowerCase();
}

export function validateFile(file) {
    if (!file) {
        return { valid: false, message: "No file was selected" };
    }

    const extension = getFileExtension(file.name);

    if (!ALLOWED_EXTENSIONS.includes(extension)) {
        return {
            valid: false,
            message: `File type not allowed. Allowed types: ${ALLOWED_EXTENSIONS.join(", ")}`,
        };
    }

    const fileSizeMB = file.size / (1024 * 1024);
    if (fileSizeMB > MAX_FILE_SIZE_MB) {
        return {
            valid: false,
            message: `File size exceeds the limit (${MAX_FILE_SIZE_MB}MB)`,
        };
    }

    return { valid: true, message: "" };
}
