import React, { useState, useRef, useCallback, useEffect } from "react"
import ChatMessageBubble from "./ChatMessage"
import LoadingState from "./LoadingState"
import MinimizedBubble from "./MinimizedBubble"
import { explainText, sendChatMessage, type ExplainParams, type ChatMessage } from "../lib/api"
import { getSettings, setSettings } from "../lib/storage"
// @ts-ignore
import iconBase64 from "data-base64:~assets/icon.png"

interface ChatBoxProps {
  hoveredText: string
  context: string
  pageUrl: string
  pageTitle: string
  pageDomain: string
  visible: boolean
  onClose: () => void
}

const ChatBox: React.FC<ChatBoxProps> = ({
  hoveredText,
  context,
  pageUrl,
  pageTitle,
  pageDomain,
  visible,
  onClose,
}) => {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [streamingContent, setStreamingContent] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [isStreaming, setIsStreaming] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [isMinimized, setIsMinimized] = useState(false)
  const [isDragging, setIsDragging] = useState(false)
  const [position, setPosition] = useState({ x: window.innerWidth - 420, y: 80 })
  const [followUpInput, setFollowUpInput] = useState("")
  const [opacityLevel, setOpacityLevel] = useState(1)
  const [selectedModel, setSelectedModel] = useState("gemma3:4b")
  const [currentProvider, setCurrentProvider] = useState("ollama")
  const [isModelDropdownOpen, setIsModelDropdownOpen] = useState(false)
  const [chatId, setChatId] = useState<string | null>(null)

  const abortRef = useRef<AbortController | null>(null)
  const dragStartRef = useRef({ x: 0, y: 0, posX: 0, posY: 0 })
  const boxRef = useRef<HTMLDivElement>(null)
  const prevTextRef = useRef("")
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages, streamingContent])

  useEffect(() => {
    getSettings().then(s => {
      if (s.model) setSelectedModel(s.model)
      if (s.provider) setCurrentProvider(s.provider)
    })
  }, [])

  useEffect(() => {
    if (!hoveredText || hoveredText === prevTextRef.current || !visible) return
    prevTextRef.current = hoveredText

    abortRef.current?.abort()
    setMessages([])
    setStreamingContent("")
    setError(null)
    setIsLoading(true)
    setIsStreaming(false)
    setChatId(null)

    const params: ExplainParams = {
      text: hoveredText,
      context,
      url: pageUrl,
      title: pageTitle,
    }

    explainText(params, {
      onChatStart: (id) => setChatId(id),
      onChunk: (chunk) => {
        setIsLoading(false)
        setIsStreaming(true)
        setStreamingContent((prev) => prev + chunk)
      },
      onDone: (fullText) => {
        setIsStreaming(false)
        setIsLoading(false)
        setMessages([
          { role: "user", content: `Explain: "${hoveredText}"` },
          { role: "assistant", content: fullText }
        ])
        setStreamingContent("")
      },
      onError: (errMsg) => {
        setError(errMsg)
        setIsLoading(false)
        setIsStreaming(false)
      },
    }).then((controller) => {
      abortRef.current = controller
    })

    return () => {
      abortRef.current?.abort()
    }
  }, [hoveredText, context, pageUrl, pageTitle, visible])

  const handleMouseDown = useCallback(
    (e: React.MouseEvent) => {
      if ((e.target as HTMLElement).closest(".hm-no-drag")) return
      setIsDragging(true)
      dragStartRef.current = {
        x: e.clientX,
        y: e.clientY,
        posX: position.x,
        posY: position.y,
      }
      e.preventDefault()
    },
    [position]
  )

  useEffect(() => {
    if (!isDragging) return
    const handleMouseMove = (e: MouseEvent) => {
      const dx = e.clientX - dragStartRef.current.x
      const dy = e.clientY - dragStartRef.current.y
      setPosition({
        x: Math.max(0, Math.min(window.innerWidth - 380, dragStartRef.current.posX + dx)),
        y: Math.max(0, Math.min(window.innerHeight - 100, dragStartRef.current.posY + dy)),
      })
    }
    const handleMouseUp = () => setIsDragging(false)
    window.addEventListener("mousemove", handleMouseMove)
    window.addEventListener("mouseup", handleMouseUp)
    return () => {
      window.removeEventListener("mousemove", handleMouseMove)
      window.removeEventListener("mouseup", handleMouseUp)
    }
  }, [isDragging])

  const handleSendMessage = () => {
    if (!followUpInput.trim() || isStreaming || isLoading) return

    const userMessage: ChatMessage = { role: "user", content: followUpInput.trim() }
    const updatedMessages = [...messages, userMessage]
    
    setMessages(updatedMessages)
    setFollowUpInput("")
    setStreamingContent("")
    setIsLoading(true)
    setError(null)
    
    abortRef.current?.abort()

    sendChatMessage({
      messages: updatedMessages,
      context,
      url: pageUrl,
      title: pageTitle,
      chat_id: chatId || undefined,
    }, {
      onChatStart: (id) => setChatId(id),
      onChunk: (chunk) => {
        setIsLoading(false)
        setIsStreaming(true)
        setStreamingContent((prev) => prev + chunk)
      },
      onDone: (fullText) => {
        setIsStreaming(false)
        setIsLoading(false)
        setMessages([...updatedMessages, { role: "assistant", content: fullText }])
        setStreamingContent("")
      },
      onError: (errMsg) => {
        setError(errMsg)
        setIsLoading(false)
        setIsStreaming(false)
      }
    }).then((controller) => {
      abortRef.current = controller
    })
  }

  if (!visible && !isMinimized) return null

  if (isMinimized) {
    return (
      <MinimizedBubble
        onClick={() => setIsMinimized(false)}
        hasContent={messages.length > 0}
      />
    )
  }

  return (
    <div
      ref={boxRef}
      className={`hm-chatbox-wrapper ${isDragging ? "hm-dragging" : ""}`}
      style={{
        left: `${position.x}px`,
        top: `${position.y}px`,
        opacity: opacityLevel,
        transition: isDragging ? "none" : "opacity 0.2s ease, transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1)",
      }}>
      <div className="hm-chatbox-glow"></div>
      <div className="hm-chatbox">
        {/* Header */}
        <div className="hm-header" onMouseDown={handleMouseDown}>
          <div className="hm-header-left">
            <div className="hm-logo">
              <img src={iconBase64} alt="OpenHover Icon" width="24" height="24" style={{ borderRadius: "50%" }} />
            </div>
            <span className="hm-title">OpenHover</span>
          </div>
          
          <div className="hm-header-controls hm-no-drag">
            <button
              className="hm-control-btn"
              onClick={() => setIsMinimized(true)}
              title="Minimize"
              aria-label="Minimize">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M5 12h14" />
              </svg>
            </button>
            <button
              className="hm-control-btn hm-close-btn"
              onClick={onClose}
              title="Close"
              aria-label="Close">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M18 6L6 18M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>

        {/* Body */}
        <div className="hm-body hm-chat-body">
          {messages.length === 0 && !isLoading && !isStreaming && !error && (
            <div className="hm-empty-state">
              <div className="hm-empty-icon">
                <img src={iconBase64} alt="OpenHover Icon" width="48" height="48" style={{ borderRadius: "50%", opacity: 0.6 }} />
              </div>
              <p className="hm-empty-text">
                Hover over any text on this page to get an instant explanation
              </p>
            </div>
          )}

          <div className="hm-chat-history">
            {messages.map((msg, i) => (
              <ChatMessageBubble key={i} role={msg.role} content={msg.content} />
            ))}

            {isStreaming && (
              <ChatMessageBubble role="assistant" content={streamingContent} isStreaming={true} />
            )}

            {isLoading && !isStreaming && <LoadingState />}

            {error && (
              <div className="hm-error">
                <span className="hm-error-icon">⚠</span>
                <span>{error}</span>
              </div>
            )}
            
            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* Follow-up input */}
        <div className="hm-footer hm-no-drag">
          <div className="hm-input-wrapper">
            <input
              type="text"
              className="hm-input"
              placeholder="Ask anything..."
              value={followUpInput}
              onChange={(e) => setFollowUpInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") handleSendMessage()
              }}
            />
            <button
              className="hm-send-btn"
              onClick={handleSendMessage}
              disabled={!followUpInput.trim() || isLoading || isStreaming}
              aria-label="Send">
              <svg
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2">
                <path d="m22 2-7 20-4-9-9-4z" />
                <path d="M22 2 11 13" />
              </svg>
            </button>
          </div>
          
          <div className="hm-footer-bottom" style={{ justifyContent: "space-between" }}>
            <div className="hm-slider-container hm-bottom-slider" style={{ width: "auto" }}>
              <span className="hm-slider-label">Opacity:</span>
              <input
                type="range"
                min="0.2"
                max="1"
                step="0.05"
                value={opacityLevel}
                onChange={(e) => setOpacityLevel(Number(e.target.value))}
                className="hm-opacity-slider hm-slider-large"
                title="Adjust Opacity"
              />
            </div>
            
            <div className="hm-model-switch" style={{ position: "relative" }}>
              <button 
                className="hm-model-select hm-model-custom-btn"
                onClick={() => {
                  getSettings().then(s => {
                    if (s.provider) setCurrentProvider(s.provider);
                    setIsModelDropdownOpen(!isModelDropdownOpen);
                  });
                }}
                title="Select AI Model"
              >
                {selectedModel} 
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ marginLeft: "4px" }}>
                  <path d="M6 9l6 6 6-6" />
                </svg>
              </button>
              
              {isModelDropdownOpen && (
                <div className="hm-model-dropdown-menu">
                  {(() => {
                    const providerModels = {
                      ollama: [
                        { val: "gemma3:4b", label: "Gemma 3 (4B)" },
                        { val: "gemma3:12b", label: "Gemma 3 (12B)" },
                        { val: "gemma3:27b", label: "Gemma 3 (27B)" },
                        { val: "gemma4:31b", label: "Gemma 4 (31B)" },
                        { val: "gpt-oss:120b", label: "GPT-OSS (120B)" },
                        { val: "gpt-oss:20b", label: "GPT-OSS (20B)" },
                        { val: "qwen3-coder:480b", label: "Qwen 3 Coder (480B)" },
                      ],
                      openai: [
                        { val: "gpt-4o", label: "GPT-4o" },
                        { val: "gpt-4-turbo", label: "GPT-4 Turbo" },
                        { val: "gpt-3.5-turbo", label: "GPT-3.5" },
                      ],
                      anthropic: [
                        { val: "claude-3-opus", label: "Claude 3 Opus" },
                        { val: "claude-3-sonnet", label: "Claude 3 Sonnet" },
                        { val: "claude-3-haiku", label: "Claude 3 Haiku" },
                      ]
                    };
                    const activeModels = providerModels[currentProvider as keyof typeof providerModels] || providerModels.ollama;
                    
                    return activeModels.map(modelOpt => (
                      <div 
                        key={modelOpt.val}
                        className={`hm-model-dropdown-item ${selectedModel === modelOpt.val ? "active" : ""}`}
                        onClick={() => {
                          setSelectedModel(modelOpt.val);
                          // @ts-ignore
                          setSettings({ model: modelOpt.val });
                          setIsModelDropdownOpen(false);
                        }}
                      >
                        {modelOpt.label}
                      </div>
                    ));
                  })()}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default ChatBox
