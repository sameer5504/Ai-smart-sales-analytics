// Matches integers/decimals with optional thousands separators and an
// optional trailing percent sign, e.g. 184,320 / 6.1% / 23 / 95.00
const NUMBER_PATTERN = /(\d[\d,]*(?:\.\d+)?%?)/g;

// Splits text on numeric tokens and wraps each one in <strong>, so key
// figures in the assistant's answer stand out the same way they do in
// the reference design - without relying on the model to emit markdown.
export function highlightNumbers(text) {
    if (!text) return null;

    const parts = text.split(NUMBER_PATTERN);

    return parts.map((part, i) =>
        i % 2 === 1 ? (
            <strong key={i} className="chatbot__number">
                {part}
            </strong>
        ) : (
            part
        ),
    );
}
