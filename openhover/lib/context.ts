import {
  IGNORED_TAGS,
  IGNORED_CLASSES,
  MIN_TEXT_LENGTH,
  MAX_CONTEXT_LENGTH,
} from "./constants"

/**
 * Check if an element is a valid text element we should respond to
 */
export function isTextElement(element: Element): boolean {
  // Skip ignored tags
  if (IGNORED_TAGS.has(element.tagName)) return false

  // Skip elements with ad-like classes
  const classList = Array.from(element.classList || [])
  const classStr = classList.join(" ").toLowerCase()
  if (IGNORED_CLASSES.some((ic) => classStr.includes(ic))) return false

  // Skip invisible elements
  const style = window.getComputedStyle(element)
  if (
    style.display === "none" ||
    style.visibility === "hidden" ||
    style.opacity === "0"
  )
    return false

  // Must have text content
  const text = getDirectTextContent(element).trim()
  if (text.length < MIN_TEXT_LENGTH) return false

  return true
}

/**
 * Get only the direct text content of an element (not children)
 */
function getDirectTextContent(element: Element): string {
  let text = ""
  for (const node of element.childNodes) {
    if (node.nodeType === Node.TEXT_NODE) {
      text += node.textContent || ""
    }
  }
  return text.trim()
}

/**
 * Extract the meaningful text from a hovered element.
 * Prefers direct text, falls back to innerText.
 */
export function extractHoveredText(element: Element): string {
  // Try direct text first
  const directText = getDirectTextContent(element)
  if (directText.length >= MIN_TEXT_LENGTH) {
    return directText.slice(0, 500)
  }

  // Fall back to innerText for container elements
  const innerText = (element as HTMLElement).innerText || element.textContent || ""
  return innerText.trim().slice(0, 500)
}

/**
 * Extract surrounding context from the element's parent and siblings
 */
export function extractSurroundingContext(
  element: Element,
  maxChars = MAX_CONTEXT_LENGTH
): string {
  const parts: string[] = []

  // Get parent's text for context
  const parent = element.parentElement
  if (parent) {
    const parentText = (parent as HTMLElement).innerText || parent.textContent || ""
    parts.push(parentText.trim())
  }

  // Get previous sibling's text
  const prevSib = element.previousElementSibling
  if (prevSib) {
    const prevText = (prevSib as HTMLElement).innerText || prevSib.textContent || ""
    if (prevText.trim()) parts.push(prevText.trim())
  }

  // Get next sibling's text
  const nextSib = element.nextElementSibling
  if (nextSib) {
    const nextText = (nextSib as HTMLElement).innerText || nextSib.textContent || ""
    if (nextText.trim()) parts.push(nextText.trim())
  }

  const combined = parts.join(" ").replace(/\s+/g, " ").trim()
  return combined.slice(0, maxChars)
}

/**
 * Get page metadata for the LLM prompt
 */
export function getPageMetadata(): {
  title: string
  url: string
  domain: string
} {
  return {
    title: document.title,
    url: window.location.href,
    domain: window.location.hostname,
  }
}

/**
 * Find the most specific text element at a point (deepest element with text)
 */
export function findTextElementAtPoint(
  x: number,
  y: number
): Element | null {
  const element = document.elementFromPoint(x, y)
  if (!element) return null

  // Walk down to the most specific text node
  let target = element
  while (target.children.length > 0) {
    let found = false
    for (const child of target.children) {
      const rect = child.getBoundingClientRect()
      if (
        x >= rect.left &&
        x <= rect.right &&
        y >= rect.top &&
        y <= rect.bottom
      ) {
        if (isTextElement(child)) {
          target = child
          found = true
          break
        }
      }
    }
    if (!found) break
  }

  return isTextElement(target) ? target : null
}
