import { useState, useRef, useEffect } from "react";
import { streamChatbotQuestion } from "../services/chatbotService";

export function useChatbot(datasetId, currency, initialQuestion = "") {
    const [messages, setMessages] = useState([]);
    const [question, setQuestion] = useState(initialQuestion);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState(null);

    const listRef = useRef(null);
    const abortControllerRef = useRef(null);

    useEffect(() => {
        if (listRef.current) {
            listRef.current.scrollTop = listRef.current.scrollHeight;
        }
    }, [messages, isLoading]);

    function updateLastAssistant(updater) {
        setMessages((prev) => {
            const next = [...prev];
            const lastIndex = next.length - 1;
            if (lastIndex < 0) return prev;
            next[lastIndex] = updater(next[lastIndex]);
            return next;
        });
    }

    async function handleSubmit(e) {
        e.preventDefault();

        const trimmed = question.trim();
        if (!trimmed || isLoading) return;

        if (!datasetId) {
            setError("Please upload a file first.");
            return;
        }

        const userMessage = { role: "user", content: trimmed };
        const historyToSend = messages.map(({ role, content }) => ({
            role,
            content,
        }));

        setMessages((prev) => [
            ...prev,
            userMessage,
            {
                role: "assistant",
                content: "",
                steps: [],
                display: null,
                streaming: true,
            },
        ]);
        setQuestion("");
        setError(null);
        setIsLoading(true);

        const controller = new AbortController();
        abortControllerRef.current = controller;

        try {
            await streamChatbotQuestion(
                trimmed,
                datasetId,
                currency,
                historyToSend,
                (event) => {
                    if (event.type === "step") {
                        updateLastAssistant((msg) => ({
                            ...msg,
                            steps: [...(msg.steps ?? []), event.label],
                        }));
                    } else if (event.type === "token") {
                        updateLastAssistant((msg) => ({
                            ...msg,
                            content: (msg.content ?? "") + event.text,
                        }));
                    } else if (event.type === "done") {
                        updateLastAssistant((msg) => ({
                            ...msg,
                            content: msg.content ? msg.content : (event.answer ?? ""),
                            display: event.display ?? null,
                            suggestions: event.suggestions ?? [],
                            streaming: false,
                        }));
                    }
                },
                controller.signal,
            );
        } catch (err) {
            if (err.name === "AbortError") {
                updateLastAssistant((msg) => ({ ...msg, streaming: false }));
            } else {
                setError(
                    "Couldn't send your question. Check your connection and try again.",
                );
                updateLastAssistant((msg) => ({ ...msg, streaming: false }));
            }
        } finally {
            setIsLoading(false);
            abortControllerRef.current = null;
        }
    }

    function handleStop() {
        abortControllerRef.current?.abort();
    }

    return {
        messages,
        question,
        setQuestion,
        isLoading,
        error,
        listRef,
        handleSubmit,
        handleStop,
    };
}
