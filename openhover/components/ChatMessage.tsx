import React from "react"

interface ChatMessageProps {
  role: "user" | "assistant" | "system"
  content: string
  isStreaming?: boolean
}

const ChatMessage: React.FC<ChatMessageProps> = ({ role, content, isStreaming }) => {
  if (role === "system") return null

  // Very basic markdown parsing for bold and line breaks
  const formatText = (text: string) => {
    let formatted = text.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
    formatted = formatted.replace(/\n/g, "<br />")
    
    // Parse list items
    formatted = formatted.replace(/^- (.*?)(?:<br \/>|$)/gm, "<li>$1</li>")
    formatted = formatted.replace(/(<li>.*<\/li>)/s, "<ul>$1</ul>")

    return { __html: formatted }
  }

  return (
    <div className={`hm-chat-message hm-msg-${role}`}>
      <div className="hm-msg-bubble">
        <div 
          className="hm-msg-content"
          dangerouslySetInnerHTML={formatText(content)}
        />
        {isStreaming && <span className="hm-cursor" />}
      </div>
    </div>
  )
}

export default ChatMessage
