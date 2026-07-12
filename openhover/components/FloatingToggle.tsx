import React, { useState, useRef, useEffect, useCallback } from "react"
import { setSettings } from "../lib/storage"
// @ts-ignore
import iconBase64 from "data-base64:~assets/icon.png"

interface FloatingToggleProps {
  enabled: boolean
  onToggle: (enabled: boolean) => void
}

const FloatingToggle: React.FC<FloatingToggleProps> = ({ enabled, onToggle }) => {
  const [isDragging, setIsDragging] = useState(false)
  
  // Use a sensible default, it will jump to this position on first mount
  const [position, setPosition] = useState({ 
    x: 24, 
    y: typeof window !== "undefined" ? window.innerHeight - 66 : 500 
  })
  
  const dragStartRef = useRef({ x: 0, y: 0, posX: 0, posY: 0 })
  const wasDraggedRef = useRef(false)

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if (e.button !== 0) return
    setIsDragging(true)
    wasDraggedRef.current = false
    dragStartRef.current = {
      x: e.clientX,
      y: e.clientY,
      posX: position.x,
      posY: position.y,
    }
    e.preventDefault()
  }, [position])

  useEffect(() => {
    if (!isDragging) return
    const handleMouseMove = (e: MouseEvent) => {
      const dx = e.clientX - dragStartRef.current.x
      const dy = e.clientY - dragStartRef.current.y
      
      if (Math.abs(dx) > 3 || Math.abs(dy) > 3) {
        wasDraggedRef.current = true
      }
      
      setPosition({
        x: Math.max(0, Math.min(window.innerWidth - 140, dragStartRef.current.posX + dx)),
        y: Math.max(0, Math.min(window.innerHeight - 42, dragStartRef.current.posY + dy)),
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

  const handleClick = async (e: React.MouseEvent) => {
    if (wasDraggedRef.current) {
      e.preventDefault()
      e.stopPropagation()
      return
    }
    const newState = !enabled
    await setSettings({ enabled: newState })
    onToggle(newState)
  }

  return (
    <button 
      className={`hm-floating-toggle ${enabled ? "hm-enabled" : "hm-disabled"} ${isDragging ? "hm-dragging" : ""}`}
      onMouseDown={handleMouseDown}
      onClick={handleClick}
      title={enabled ? "Disable OpenHover" : "Enable OpenHover"}
      aria-label="Toggle OpenHover"
      style={{
        left: `${position.x}px`,
        top: `${position.y}px`,
        bottom: 'auto',
        right: 'auto',
      }}
    >
      <div className="hm-toggle-icon">
        <img 
          src={iconBase64} 
          alt="OpenHover Icon" 
          width="18" 
          height="18" 
          style={{ 
            borderRadius: "50%", 
            opacity: enabled ? 1 : 0.5,
            filter: enabled ? "drop-shadow(0 0 4px rgba(139, 92, 246, 0.6))" : "grayscale(100%)",
            transition: "all 0.3s ease"
          }} 
        />
      </div>
      <span className="hm-toggle-text">OpenHover {enabled ? "ON" : "OFF"}</span>
    </button>
  )
}

export default FloatingToggle
