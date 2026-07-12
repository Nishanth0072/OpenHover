import React, { useEffect, useState } from "react"

import { getSettings, setSettings, removeExcludedSite, addExcludedSite, type OpenHoverSettings } from "~lib/storage"
import { DEFAULT_SETTINGS } from "~lib/constants"
import AuthScreen from "./components/AuthScreen"

import "./options.css"

function Popup() {
  const [settings, setLocalSettings] = useState<OpenHoverSettings>(DEFAULT_SETTINGS)
  const [newSite, setNewSite] = useState("")
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    getSettings().then(setLocalSettings)
  }, [])

  const updateSetting = async <K extends keyof OpenHoverSettings>(
    key: K,
    value: OpenHoverSettings[K]
  ) => {
    const updated = await setSettings({ [key]: value })
    setLocalSettings(updated)
    showSaved()

    // Notify content scripts of settings change
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (tabs[0]?.id) {
        chrome.tabs.sendMessage(tabs[0].id, { type: "settings-changed" }).catch(() => {})
      }
    })
  }

  const showSaved = () => {
    setSaved(true)
    setTimeout(() => setSaved(false), 1500)
  }

  const handleAddSite = async () => {
    if (!newSite.trim()) return
    await addExcludedSite(newSite.trim())
    const updated = await getSettings()
    setLocalSettings(updated)
    setNewSite("")
    showSaved()
  }

  const handleRemoveSite = async (site: string) => {
    await removeExcludedSite(site)
    const updated = await getSettings()
    setLocalSettings(updated)
    showSaved()
  }

  const handleLogout = async () => {
    await updateSetting("accessToken", "")
  }

  if (!settings.accessToken) {
    return (
      <AuthScreen 
        onSuccess={(token) => updateSetting("accessToken", token)} 
      />
    )
  }

  return (
    <div className="hm-popup">
      {/* Header */}
      <div className="hm-popup-header">
        <div className="hm-popup-logo">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10" />
            <path d="M12 16v-4" />
            <path d="M12 8h.01" />
          </svg>
        </div>
        <div className="hm-popup-title-group">
          <h1 className="hm-popup-title">OpenHover</h1>
          <span className="hm-popup-version">v0.0.1</span>
        </div>
        {saved && <span className="hm-saved-badge">✓ Saved</span>}
      </div>

      {/* Global Toggle */}
      <div className="hm-popup-section">
        <div className="hm-toggle-row">
          <div className="hm-toggle-info">
            <span className="hm-toggle-label">Enable OpenHover</span>
            <span className="hm-toggle-desc">Show explanations when hovering text</span>
          </div>
          <label className="hm-switch">
            <input
              type="checkbox"
              checked={settings.enabled}
              onChange={(e) => updateSetting("enabled", e.target.checked)}
            />
            <span className="hm-slider" />
          </label>
        </div>
      </div>

      {/* AI Provider */}
      <div className="hm-popup-section">
        <h2 className="hm-section-title">AI Provider</h2>
        <div className="hm-radio-group">
          {(["openai", "ollama", "anthropic"] as const).map((prov) => (
            <label key={prov} className={`hm-radio-option ${settings.provider === prov ? "active" : ""}`}>
              <input
                type="radio"
                name="provider"
                value={prov}
                checked={settings.provider === prov}
                onChange={() => updateSetting("provider", prov)}
              />
              <span className="hm-radio-dot" />
              <span className="hm-radio-text">
                {prov === "openai" ? "OpenAI" : prov === "ollama" ? "Ollama" : "Anthropic"}
              </span>
            </label>
          ))}
        </div>
      </div>

      {/* Trigger Settings */}
      <div className="hm-popup-section">
        <h2 className="hm-section-title">Trigger Mode</h2>
        <div className="hm-radio-group">
          {(["hover", "select", "click"] as const).map((mode) => (
            <label key={mode} className={`hm-radio-option ${settings.triggerMode === mode ? "active" : ""}`}>
              <input
                type="radio"
                name="triggerMode"
                value={mode}
                checked={settings.triggerMode === mode}
                onChange={() => updateSetting("triggerMode", mode)}
              />
              <span className="hm-radio-dot" />
              <span className="hm-radio-text">
                {mode === "hover" ? "🖱️ Hover" : mode === "select" ? "📝 Select" : "👆 Click Icon"}
              </span>
            </label>
          ))}
        </div>
      </div>

      {/* Account / Logout */}
      <div className="hm-popup-section">
        <h2 className="hm-section-title">Account</h2>
        <div className="hm-input-wrapper">
          <button className="hm-auth-btn" style={{ backgroundColor: '#da3633', width: '100%' }} onClick={handleLogout}>
            Log Out
          </button>
        </div>
      </div>

      {/* Hover Delay */}
      <div className="hm-popup-section">
        <div className="hm-slider-header">
          <h2 className="hm-section-title">Hover Delay</h2>
          <span className="hm-slider-value">{settings.hoverDelay}ms</span>
        </div>
        <input
          type="range"
          className="hm-range"
          min={200}
          max={1500}
          step={100}
          value={settings.hoverDelay}
          onChange={(e) => updateSetting("hoverDelay", parseInt(e.target.value))}
        />
        <div className="hm-range-labels">
          <span>Fast</span>
          <span>Slow</span>
        </div>
      </div>

      {/* Response Length */}
      <div className="hm-popup-section">
        <h2 className="hm-section-title">Response Length</h2>
        <div className="hm-segmented">
          {(["concise", "detailed"] as const).map((len) => (
            <button
              key={len}
              className={`hm-seg-btn ${settings.responseLength === len ? "active" : ""}`}
              onClick={() => updateSetting("responseLength", len)}>
              {len === "concise" ? "⚡ Concise" : "📖 Detailed"}
            </button>
          ))}
        </div>
      </div>

      {/* Excluded Sites */}
      <div className="hm-popup-section">
        <h2 className="hm-section-title">Excluded Sites</h2>
        <div className="hm-add-site">
          <input
            type="text"
            className="hm-site-input"
            placeholder="e.g., bank.com"
            value={newSite}
            onChange={(e) => setNewSite(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleAddSite()}
          />
          <button className="hm-add-btn" onClick={handleAddSite} disabled={!newSite.trim()}>
            Add
          </button>
        </div>
        {settings.excludedSites.length > 0 && (
          <div className="hm-site-list">
            {settings.excludedSites.map((site) => (
              <div key={site} className="hm-site-item">
                <span className="hm-site-name">{site}</span>
                <button className="hm-site-remove" onClick={() => handleRemoveSite(site)} aria-label="Remove">
                  ×
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="hm-popup-footer">
        <span className="hm-footer-text">OpenHover — Your AI reading companion</span>
      </div>
    </div>
  )
}

export default Popup
