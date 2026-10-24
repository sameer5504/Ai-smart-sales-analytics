import { useLocation } from "react-router-dom";
import MappingReviewScreen from "../components/MappingReviewScreen.jsx";

// A failed upload arrives here via UploadPage's navigate(..., { state }) with
// the file's identity, real columns, and the currency selected on the upload
// page, so the review screen can finish that exact upload. Arriving without
// that state (e.g. a direct link) falls back to the standalone
// paste-your-columns tool.
export default function MappingReviewPage() {
    const location = useLocation();
    const { filename, dataType, columns, currency } = location.state || {};

    return (
        <MappingReviewScreen
            filename={filename}
            dataType={dataType}
            initialColumns={columns}
            currency={currency}
        />
    );
}
