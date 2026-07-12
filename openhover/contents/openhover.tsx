import cssText from "data-text:./openhover.css"
import type { PlasmoCSConfig, PlasmoGetOverlayAnchor, PlasmoGetShadowHostId } from "plasmo"
import React, { useCallback, useEffect, useRef, useState } from "react"

import ChatBox from "~components/ChatBox"
import {
  extractHoveredText,
  extractSurroundingContext,
  findTextElementAtPoint,
  getPageMetadata,
  isTextElement,
} from "~lib/context"
import { getSettings, isSiteExcluded, isExtensionEnabled } from "~lib/storage"
import { HOVER_DEBOUNCE_MS, MIN_TEXT_LENGTH } from "~lib/constants"

// Plasmo content script config
export const config: PlasmoCSConfig = {
  matches: ["<all_urls>"],
  all_frames: false,
}

import FloatingToggle from "~components/FloatingToggle"

// Inject our CSS into the Shadow DOM
export const getStyle = () => {
  const style = document.createElement("style")
  style.textContent = cssText
  return style
}

export const getShadowHostId = () => "openhover-host"

// Main overlay component — rendered inside Shadow DOM by Plasmo
const OpenHoverOverlay = () => {
  const [hoveredText, setHoveredText] = useState("")
  const [context, setContext] = useState("")
  const [visible, setVisible] = useState(false)
  const [enabled, setEnabled] = useState(true)

  const hoverTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const lastElementRef = useRef<Element | null>(null)
  const hostRef = useRef<HTMLElement | null>(null)

  // Check if extension is enabled on this site
  useEffect(() => {
    const checkEnabled = async () => {
      const globalEnabled = await isExtensionEnabled()
      const excluded = await isSiteExcluded(window.location.hostname)
      setEnabled(globalEnabled && !excluded)
    }
    checkEnabled()

    // Listen for settings changes
    const handleMessage = (message: any) => {
      if (message.type === "settings-changed") {
        checkEnabled()
      }
    }
    chrome.runtime.onMessage.addListener(handleMessage)
    return () => chrome.runtime.onMessage.removeListener(handleMessage)
  }, [])

  // Setup hover detection
  useEffect(() => {
    if (!enabled) {
      // If disabled, ensure we close the chatbox and clean up
      if (visible) {
        setVisible(false)
        setHoveredText("")
        setContext("")
        lastElementRef.current = null
      }
      return
    }

    const handleMouseOver = async (e: MouseEvent) => {
      // Don't trigger on our own overlay
      const shadowHost = document.getElementById("openhover-host")
      if (shadowHost?.contains(e.target as Node)) return

      // Clear previous timer
      if (hoverTimerRef.current) {
        clearTimeout(hoverTimerRef.current)
      }

      const target = e.target as Element
      if (!target || !isTextElement(target)) return

      // Don't re-trigger on same element
      if (target === lastElementRef.current) return

      // Get delay from settings
      const settings = await getSettings()

      hoverTimerRef.current = setTimeout(() => {
        const text = extractHoveredText(target)
        if (text.length < MIN_TEXT_LENGTH) return

        lastElementRef.current = target
        const surroundingContext = extractSurroundingContext(target)
        setHoveredText(text)
        setContext(surroundingContext)
        setVisible(true)
      }, settings.hoverDelay || HOVER_DEBOUNCE_MS)
    }

    const handleMouseOut = () => {
      if (hoverTimerRef.current) {
        clearTimeout(hoverTimerRef.current)
        hoverTimerRef.current = null
      }
    }

    document.addEventListener("mouseover", handleMouseOver, { passive: true })
    document.addEventListener("mouseout", handleMouseOut, { passive: true })

    return () => {
      document.removeEventListener("mouseover", handleMouseOver)
      document.removeEventListener("mouseout", handleMouseOut)
      if (hoverTimerRef.current) clearTimeout(hoverTimerRef.current)
    }
  }, [enabled, visible])

  const handleClose = useCallback(() => {
    setVisible(false)
    setHoveredText("")
    setContext("")
    lastElementRef.current = null
  }, [])

  const { title, url, domain } = getPageMetadata()

  return (
    <div id="openhover-root">
      {enabled && (
        <ChatBox
          hoveredText={hoveredText}
          context={context}
          pageUrl={url}
          pageTitle={title}
          pageDomain={domain}
          visible={visible}
          onClose={handleClose}
        />
      )}
      <FloatingToggle enabled={enabled} onToggle={setEnabled} />
    </div>
  )
}

export default OpenHoverOverlay
