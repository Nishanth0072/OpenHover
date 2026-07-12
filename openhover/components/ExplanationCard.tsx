import React from "react"

interface ExplanationCardProps {
  hoveredText: string
  explanation: string
  isStreaming: boolean
  domain: string
  suggestedQuestions?: string[]
  onQuestionClick?: (question: string) => void
  onThumbsUp?: () => void
  onThumbsDown?: () => void
}

const ExplanationCard: React.FC<ExplanationCardProps> = ({
  hoveredText,
  explanation,
  isStreaming,
  domain,
  suggestedQuestions = [],
  onQuestionClick,
  onThumbsUp,
  onThumbsDown,
}) => {
  // Simple markdown-like rendering (bold, italic, code, lists)
  function renderMarkdown(text: string): React.ReactNode {
    const lines = text.split("\n")
    return lines.map((line, i) => {
      // Headers
      if (line.startsWith("### "))
        return (
          <h4 key={i} className="hm-md-h4">
            {line.slice(4)}
          </h4>
        )
      if (line.startsWith("## "))
        return (
          <h3 key={i} className="hm-md-h3">
            {line.slice(3)}
          </h3>
        )

      // Bullet points
      if (line.startsWith("- ") || line.startsWith("* "))
        return (
          <li key={i} className="hm-md-li">
            {renderInline(line.slice(2))}
          </li>
        )

      // Numbered lists
      const numberedMatch = line.match(/^\d+\.\s(.+)/)
      if (numberedMatch)
        return (
          <li key={i} className="hm-md-li hm-md-ol">
            {renderInline(numberedMatch[1])}
          </li>
        )

      // Empty lines
      if (!line.trim()) return <br key={i} />

      // Regular paragraph
      return (
        <p key={i} className="hm-md-p">
          {renderInline(line)}
        </p>
      )
    })
  }

  function renderInline(text: string): React.ReactNode {
    // Replace **bold**, *italic*, `code`
    const parts = text.split(/(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)/g)
    return parts.map((part, i) => {
      if (part.startsWith("**") && part.endsWith("**"))
        return (
          <strong key={i} className="hm-md-bold">
            {part.slice(2, -2)}
          </strong>
        )
      if (part.startsWith("*") && part.endsWith("*"))
        return (
          <em key={i} className="hm-md-italic">
            {part.slice(1, -1)}
          </em>
        )
      if (part.startsWith("`") && part.endsWith("`"))
        return (
          <code key={i} className="hm-md-code">
            {part.slice(1, -1)}
          </code>
        )
      return part
    })
  }

  return (
    <div className="hm-explanation-card">
      {/* Hovered text highlight */}
      <div className="hm-hovered-text">
        <span className="hm-hovered-label">Hovered</span>
        <span className="hm-hovered-content">"{hoveredText}"</span>
      </div>

      {/* Explanation content */}
      <div className="hm-explanation-content">
        {renderMarkdown(explanation)}
        {isStreaming && <span className="hm-cursor-blink">▊</span>}
      </div>

      {/* Suggested follow-up questions */}
      {suggestedQuestions.length > 0 && !isStreaming && (
        <div className="hm-suggestions">
          <span className="hm-suggestions-label">Follow up:</span>
          <div className="hm-suggestion-chips">
            {suggestedQuestions.map((q, i) => (
              <button
                key={i}
                className="hm-suggestion-chip"
                onClick={() => onQuestionClick?.(q)}>
                {q}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Footer: feedback + domain badge */}
      {!isStreaming && explanation && (
        <div className="hm-card-footer">
          <span className="hm-domain-badge">{domain}</span>
          <div className="hm-feedback-buttons">
            <button
              className="hm-feedback-btn"
              onClick={onThumbsUp}
              title="Helpful"
              aria-label="Mark as helpful">
              <svg
                width="14"
                height="14"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2">
                <path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3" />
              </svg>
            </button>
            <button
              className="hm-feedback-btn"
              onClick={onThumbsDown}
              title="Not helpful"
              aria-label="Mark as not helpful">
              <svg
                width="14"
                height="14"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2">
                <path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17" />
              </svg>
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

export default ExplanationCard
