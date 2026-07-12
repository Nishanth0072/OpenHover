import React from "react"

const LoadingState: React.FC = () => {
  return (
    <div className="hm-loading">
      <div className="hm-loading-dots">
        <div className="hm-dot" style={{ animationDelay: "0ms" }} />
        <div className="hm-dot" style={{ animationDelay: "150ms" }} />
        <div className="hm-dot" style={{ animationDelay: "300ms" }} />
      </div>
      <p className="hm-loading-text">Analyzing text...</p>
    </div>
  )
}

export default LoadingState
