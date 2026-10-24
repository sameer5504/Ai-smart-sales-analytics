import { authFetch } from "../../../shared/utils/authFetch";

const API_URL = import.meta.env.VITE_API_URL;

const CHATBOT_ENDPOINT = `${API_URL}/chatbot/ask`;
const CHATBOT_STREAM_ENDPOINT = `${API_URL}/chatbot/ask/stream`;

// Kept for any caller that doesn't need live streaming.
export async function sendChatbotQuestion(question, datasetId, currency, history = []) {
    const response = await authFetch(CHATBOT_ENDPOINT, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, dataset_id: datasetId, currency, history }),
    });

    if (!response.ok) {
        throw new Error("Request failed");
    }

    return response.json();
}

// Streams the answer live.
export async function streamChatbotQuestion(
    question,
    datasetId,
    currency,
    history = [],
    onEvent,
    signal,
) {
    const response = await authFetch(CHATBOT_STREAM_ENDPOINT, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, dataset_id: datasetId, currency, history }),
        signal,
    });

    if (!response.ok || !response.body) {
        throw new Error("Request failed");
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
            if (!line.trim()) continue;

            try {
                onEvent(JSON.parse(line));
            } catch {
                // Ignore malformed/partial lines.
            }
        }
    }

    if (buffer.trim()) {
        try {
            onEvent(JSON.parse(buffer));
        } catch {
            // Ignore trailing partial data.
        }
    }
}
