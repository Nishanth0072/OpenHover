import React from "react"
// @ts-ignore
import bubbleIconBase64 from "data-base64:~assets/bubble-icon.png"

interface MinimizedBubbleProps {
  onClick: () => void
  hasContent: boolean
}

const MinimizedBubble: React.FC<MinimizedBubbleProps> = ({
  onClick,
  hasContent,
}) => {
  return (
    <button
      className="hm-minimized-bubble"
      onClick={onClick}
      title="Open OpenHover"
      aria-label="Open OpenHover chatbox"
      style={{ padding: 0, overflow: "hidden", background: "transparent", border: "none" }}>
      <img src={bubbleIconBase64} alt="OpenHover Icon" width="52" height="52" style={{ objectFit: "cover", display: "block" }} />
      {hasContent && <span className="hm-bubble-indicator" />}
    </button>
  )
}

export default MinimizedBubble
