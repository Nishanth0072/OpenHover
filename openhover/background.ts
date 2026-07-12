import { Storage } from "@plasmohq/storage"
import { DEFAULT_SETTINGS, type OpenHoverSettings } from "~lib/constants"

const storage = new Storage({ area: "local" })

// Listen for messages from content scripts and popup
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "check-enabled") {
    handleCheckEnabled(message.domain).then(sendResponse)
    return true // async response
  }

  if (message.type === "get-settings") {
    getStoredSettings().then(sendResponse)
    return true
  }

  return false
})

/**
 * Check if the extension is enabled for a given domain
 */
async function handleCheckEnabled(domain: string): Promise<{ enabled: boolean }> {
  const settings = await getStoredSettings()

  if (!settings.enabled) {
    return { enabled: false }
  }

  const isExcluded = settings.excludedSites.some(
    (site) =>
      domain.toLowerCase().includes(site.toLowerCase()) ||
      site.toLowerCase().includes(domain.toLowerCase())
  )

  return { enabled: !isExcluded }
}

/**
 * Get settings from storage
 */
async function getStoredSettings(): Promise<OpenHoverSettings> {
  const stored = await storage.get<Partial<OpenHoverSettings>>("openhover_settings")
  return { ...DEFAULT_SETTINGS, ...stored }
}

// Extension install/update handler
chrome.runtime.onInstalled.addListener(async (details) => {
  if (details.reason === "install") {
    // Set defaults on first install
    await storage.set("openhover_settings", DEFAULT_SETTINGS)
    console.log("🧠 OpenHover installed — defaults set")
  }
})

export {}
