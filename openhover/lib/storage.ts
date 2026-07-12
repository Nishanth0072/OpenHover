import { Storage } from "@plasmohq/storage"
import { DEFAULT_SETTINGS, type OpenHoverSettings } from "./constants"

export type { OpenHoverSettings }


const storage = new Storage({ area: "local" })

const SETTINGS_KEY = "openhover_settings"

/**
 * Get all settings, merged with defaults
 */
export async function getSettings(): Promise<OpenHoverSettings> {
  const stored = await storage.get<Partial<OpenHoverSettings>>(SETTINGS_KEY)
  return { ...DEFAULT_SETTINGS, ...stored }
}

/**
 * Update settings (partial merge)
 */
export async function setSettings(
  partial: Partial<OpenHoverSettings>
): Promise<OpenHoverSettings> {
  const current = await getSettings()
  const updated = { ...current, ...partial }
  await storage.set(SETTINGS_KEY, updated)
  return updated
}

/**
 * Check if the extension is globally enabled
 */
export async function isExtensionEnabled(): Promise<boolean> {
  const settings = await getSettings()
  return settings.enabled
}

/**
 * Check if a specific site is excluded
 */
export async function isSiteExcluded(domain: string): Promise<boolean> {
  const settings = await getSettings()
  return settings.excludedSites.some(
    (excluded) =>
      domain.toLowerCase().includes(excluded.toLowerCase()) ||
      excluded.toLowerCase().includes(domain.toLowerCase())
  )
}

/**
 * Add a site to the exclusion list
 */
export async function addExcludedSite(domain: string): Promise<void> {
  const settings = await getSettings()
  if (!settings.excludedSites.includes(domain.toLowerCase())) {
    settings.excludedSites.push(domain.toLowerCase())
    await setSettings({ excludedSites: settings.excludedSites })
  }
}

/**
 * Remove a site from the exclusion list
 */
export async function removeExcludedSite(domain: string): Promise<void> {
  const settings = await getSettings()
  settings.excludedSites = settings.excludedSites.filter(
    (s) => s !== domain.toLowerCase()
  )
  await setSettings({ excludedSites: settings.excludedSites })
}
