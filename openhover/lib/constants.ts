// OpenHover constants and default settings

export const API_BASE_URL = "http://127.0.0.1:8000"

export const DEFAULT_SETTINGS = {
  enabled: true,
  triggerMode: "hover" as "hover" | "select" | "click",
  hoverDelay: 600,
  responseLength: "concise" as "concise" | "detailed",
  provider: "openai" as "openai" | "ollama" | "anthropic",
  model: "gemma3:4b" as string,
  accessToken: "", // Add access token
  excludedSites: [] as string[],
  darkMode: "auto" as "auto" | "light" | "dark",
  chatboxPosition: { x: -1, y: -1 } as { x: number; y: number },
}

export type OpenHoverSettings = typeof DEFAULT_SETTINGS

export const OVERLAY_Z_INDEX = 2147483647 // Max z-index

export const MIN_TEXT_LENGTH = 2
export const MAX_TEXT_LENGTH = 2000
export const MAX_CONTEXT_LENGTH = 3000

export const HOVER_DEBOUNCE_MS = 600

// Elements to ignore for hover detection
export const IGNORED_TAGS = new Set([
  "SCRIPT",
  "STYLE",
  "NOSCRIPT",
  "IFRAME",
  "IMG",
  "VIDEO",
  "AUDIO",
  "CANVAS",
  "SVG",
  "INPUT",
  "TEXTAREA",
  "SELECT",
  "BUTTON",
  "NAV",
  "HEADER",
  "FOOTER",
])

// Elements that usually contain ads or non-content
export const IGNORED_CLASSES = [
  "ad",
  "ads",
  "advert",
  "advertisement",
  "banner",
  "sidebar",
  "nav",
  "menu",
  "footer",
  "header",
]
