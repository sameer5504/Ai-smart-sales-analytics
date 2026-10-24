import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { useChatbot } from "../hooks/useChatbot";
import { useDatasetContext } from "../../../shared/context/DatasetContext";
import DisplayBlock from "./DisplayBlock";
import { highlightNumbers } from "../utils/highlightNumbers";
import "./Chatbot.css";

const SUGGESTED_QUESTIONS = [
    {
        group: "Understand a number",
        items: [
            "What is the highest selling product?",
            "Why did revenue change last month?",
            "Which products earned the most?",
        ],
    },
    {
        group: "Look ahead",
        items: [
            "What's the forecast for next month?",
            "Should I expect a seasonal change?",
        ],
    },
    {
        group: "About your data",
        items: ["What can you tell me from my file?"],
    },
];

function AssistantContent({ message }) {
    const { content, steps, streaming } = message;
    const hasSteps = steps && steps.length > 0;
    const hasContent = Boolean(content);

    return (
        <>
            {hasSteps && (
                <div className="chatbot__steps">
                    {steps.map((step, idx) => (
                        <div className="chatbot__step" key={idx}>
                            <span className="chatbot__step-icon" aria-hidden="true">
                                ✓
                            </span>
                            <span dir="auto">{step}</span>
                        </div>
                    ))}
                </div>
            )}

            {!hasContent && streaming ? (
                <span className="chatbot__thinking">Thinking…</span>
            ) : (
                <span>{highlightNumbers(content)}</span>
            )}
        </>
    );
}

export default function Chatbot() {
    // Same dataset AppLayout's topbar selector has set - shared via
    // DatasetContext, so switching the file anywhere updates it everywhere.
    // currency comes from the dataset's own record (set at upload time),
    // never sessionStorage - each file keeps its own currency.
    const { datasetId, currentDataset } = useDatasetContext();
    const currency = currentDataset?.currency;

    const location = useLocation();
    const navigate = useNavigate();

    // Read once, while this screen first renders. The dashboard sends the
    // question through the navigation rather than storing it anywhere, so
    // arriving any other way simply leaves the box empty.
    const [openingQuestion] = useState(() => location.state?.prompt ?? null);
    const [cameFromDashboard, setCameFromDashboard] = useState(
        Boolean(location.state?.prompt),
    );

    // Drop the question from the history entry once it has been read, so
    // coming back to this screen later does not type it out again.
    useEffect(() => {
        if (location.state?.prompt) {
            navigate(location.pathname, { replace: true, state: null });
        }
    }, [location, navigate]);

    const {
        messages,
        question,
        setQuestion,
        isLoading,
        error,
        listRef,
        handleSubmit,
        handleStop,
    } = useChatbot(datasetId, currency, openingQuestion ?? "");

    // The note belongs to the unsent question. Once anything has been asked,
    // the conversation speaks for itself.
    const showOpeningNote = cameFromDashboard && messages.length === 0;

    function clearOpeningQuestion() {
        setQuestion("");
        setCameFromDashboard(false);
    }

    return (
        <div className="chatbot">
            <div className="chatbot__messages" ref={listRef}>
                {messages.length === 0 && (
                    <div className="chatbot__empty">
                        <div className="chatbot__empty-icon" aria-hidden="true">
                            <svg viewBox="0 0 24 24" width="16" height="16" fill="none">
                                <path
                                    d="M12 2.5 13.7 8l5.5 1.7-5.5 1.7L12 17l-1.7-5.6L4.8 9.7l5.5-1.7L12 2.5Z"
                                    fill="currentColor"
                                />
                            </svg>
                        </div>

                        <p className="chatbot__empty-title">Ask about your data</p>

                        <p className="chatbot__empty-subtitle">
                            Have a question about your data? Just ask.
                        </p>

                        {SUGGESTED_QUESTIONS.map((group) => (
                            <div className="chatbot__group" key={group.group}>
                                <p className="chatbot__group-label">{group.group}</p>

                                {group.items.map((q) => (
                                    <button
                                        key={q}
                                        type="button"
                                        className="chatbot__suggestion"
                                        onClick={() => setQuestion(q)}
                                    >
                                        {q}
                                    </button>
                                ))}
                            </div>
                        ))}
                    </div>
                )}

                {messages.map((msg, i) => {
                    const isLastMessage = i === messages.length - 1;
                    const isLastAssistantStreaming =
                        msg.role === "assistant" && msg.streaming && isLastMessage;

                    const showFollowups =
                        msg.role === "assistant" &&
                        !msg.streaming &&
                        isLastMessage &&
                        !isLoading &&
                        msg.suggestions &&
                        msg.suggestions.length > 0;

                    return (
                        <div
                            key={i}
                            className={
                                msg.role === "user"
                                    ? "chatbot__row chatbot__row--user"
                                    : "chatbot__row chatbot__row--assistant"
                            }
                        >
                            <div className="chatbot__row-content">
                                <div
                                    className={
                                        msg.role === "user"
                                            ? "chatbot__bubble chatbot__bubble--user"
                                            : "chatbot__bubble chatbot__bubble--assistant"
                                    }
                                    dir="auto"
                                >
                                    {msg.role === "assistant" ? (
                                        <AssistantContent message={msg} />
                                    ) : (
                                        msg.content
                                    )}

                                    {msg.role === "assistant" && (
                                        <DisplayBlock display={msg.display} />
                                    )}
                                </div>

                                {isLastAssistantStreaming && (
                                    <button
                                        type="button"
                                        className="chatbot__stop"
                                        onClick={handleStop}
                                    >
                                        Stop
                                    </button>
                                )}

                                {showFollowups && (
                                    <div className="chatbot__followups">
                                        {msg.suggestions.map((q, idx) => (
                                            <button
                                                key={q}
                                                type="button"
                                                className={`chatbot__followup-chip chatbot__followup-chip--${
                                                    idx === 0
                                                        ? "primary"
                                                        : idx === 1
                                                          ? "outline"
                                                          : "ghost"
                                                }`}
                                                onClick={() => setQuestion(q)}
                                            >
                                                {q}
                                            </button>
                                        ))}
                                    </div>
                                )}
                            </div>
                        </div>
                    );
                })}
            </div>

            {error && <div className="chatbot__error">{error}</div>}

            {showOpeningNote && (
                <div className="chatbot__opening-note">
                    <span className="chatbot__opening-tag">
                        Started from your dashboard
                    </span>

                    <button
                        type="button"
                        className="chatbot__opening-clear"
                        onClick={clearOpeningQuestion}
                    >
                        Clear
                    </button>
                </div>
            )}

            <form className="chatbot__input-bar" onSubmit={handleSubmit}>
                <input
                    type="text"
                    className="chatbot__input"
                    placeholder="Write your question here..."
                    value={question}
                    onChange={(e) => setQuestion(e.target.value)}
                    disabled={isLoading}
                />

                <button
                    type="submit"
                    className="chatbot__send"
                    disabled={isLoading || !question.trim()}
                >
                    Send
                </button>
            </form>
        </div>
    );
}
