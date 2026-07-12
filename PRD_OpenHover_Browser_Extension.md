# Product Requirements Document (PRD)

## Product Name
**HoverMind** (working title)
*A browser extension that overlays an AI chatbox on top of any website, explaining whatever text the user hovers over.*

---

## 1. Overview

### 1.1 Problem Statement
Users read content across many different websites (news, docs, research papers, product pages, contracts, dashboards) and frequently encounter text they don't understand. Currently they must copy text and search elsewhere, breaking their reading flow, or give up.

### 1.2 Proposed Solution
A **browser extension** that works on **any website** (not limited to one site). When the user hovers over text, the extension:
1. Captures the hovered text + surrounding page context
2. Opens a floating chatbox **overlaid on top of the browser page** (like a persistent side panel or floating widget)
3. Shows an AI-generated explanation of that text
4. Lets the user ask follow-up questions in the same chatbox

### 1.3 Key Difference from Site-Embedded Widget
| | Embedded Widget (v1 idea) | Browser Extension (this version) |
|---|---|---|
| Where it works | Only sites that install the script | **Any website** the user visits |
| Installed by | Website owner | **End user** (via Chrome/Edge/Firefox store) |
| Rendering | Part of the page DOM | **Injected overlay**, independent of page |
| Content access | Site owner controls what's explainable | Extension reads **whatever is on screen** |

### 1.4 Goals
- Let users get instant, in-context explanations on **any webpage** without leaving it
- Reduce tab-switching to search engines/dictionaries
- Provide a universal "reading companion" experience
- Build a product that's distributable via browser extension stores (Chrome Web Store, Firefox Add-ons, Edge Add-ons)

### 1.5 Non-Goals (v1)
- Not modifying or interacting with the website's own functionality (read-only overlay)
- Not designed for sites requiring login/paywalled content scraping beyond what's visibly rendered
- No transactional actions (won't fill forms, click buttons, etc.)

---

## 2. Target Users

| User Type | Need |
|---|---|
| General web reader | Quick explanations while reading any site |
| Students / researchers | Understand jargon/complex text on papers, articles |
| Professionals (legal, technical, medical reading) | Instant clarification without leaving the page |
| Non-native language readers | Simplified explanations of unfamiliar terms/phrases |

---

## 3. User Stories

1. As a user, I install the extension once and it works on every website I visit.
2. As a user, when I hover over any text on any page, I see a floating chatbox appear with an explanation.
3. As a user, I can ask follow-up questions about the hovered text without switching tabs.
4. As a user, I can toggle the extension on/off per site or globally.
5. As a user, I want the overlay to not break or visually clash with the underlying website.
6. As a user, I want my browsing/hover data handled privately and not stored without my consent.

---

## 4. Core Features (v1 Scope)

### 4.1 Browser Extension Shell
- Works as a **Chrome/Edge (Manifestv3) extension**, with Firefox support as stretch goal
- Injected via **content script** into every page the user visits
- Toggle via extension icon (on/off), plus per-site enable/disable

### 4.2 Hover/Select Trigger
- Hover with configurable delay (default ~600ms) OR text selection (user preference)
- Works across arbitrary DOM structures (news sites, PDFs-in-browser, docs, dashboards)
- Ignores non-text elements (images, ads, nav menus) by default — configurable

### 4.3 Floating Overlay Chatbox
- Renders as a **shadow DOM overlay** (isolated styling, won't conflict with host page CSS)
- Positioned as a floating side panel (draggable/dockable: right edge default)
- Always-on-top (`z-index` max), independent of page scroll/layout
- Persistent across hovers within the same page/tab session
- Minimize / close / resize controls
- Does not block page interaction when minimized

### 4.4 Context-Aware AI Response Engine
- **Input:** hovered/selected text + surrounding DOM text (parent/sibling elements) + page URL + page title
- **Output:** concise explanation + option to expand + suggested follow-up questions
- Follow-up Q&A maintains context of that specific hover + page

### 4.5 Privacy & Permissions
- Extension requests only necessary permissions (`activeTab`, content script injection)
- Clear consent flow: user informed that hovered text + page context is sent to AI backend
- Option to exclude specific sites (e.g., banking, email) from the extension entirely
- No storage of full page content — only the specific hovered snippet + minimal context, discarded after session unless user opts into history

### 4.6 Settings Panel (Extension Popup)
- Enable/disable globally or per-site
- Trigger mode: hover vs. select vs. click-icon
- Response length: concise / detailed
- Site exclusion list
- Clear conversation history

---

## 5. System Architecture (High-Level)

```
[Browser Extension]
  ├── Content Script (injected into every page)
  │     - Detects hover/selection
  │     - Extracts text + surrounding context
  │     - Renders overlay chatbox (Shadow DOM)
  │
  ├── Background Service Worker
  │     - Manages API calls to backend
  │     - Handles auth/session state
  │     - Applies site-exclusion rules
  │
  └── Extension Popup UI
        - Settings, on/off toggle, history

        |
        v
[Backend API Gateway]
        |
        v
[LLM / Context-QA Service]
   - Prompted LLM (e.g., Claude API)
   - Optional: web-context enrichment for niche terms
        |
        v
[Response returned to Content Script → rendered in overlay]
```

### 5.1 Components
| Component | Description |
|---|---|
| **Content Script** | Runs on every page; detects hover/select, extracts context, injects overlay UI |
| **Shadow DOM Overlay UI** | Isolated chatbox UI that visually sits on top of any site without style conflicts |
| **Background Service Worker** | Handles extension-level logic, API communication, cross-tab state |
| **Backend API** | Auth, rate limiting, request routing to LLM, logging (privacy-respecting) |
| **LLM Layer** | Claude (or similar) generates explanations grounded in the captured context |
| **Extension Settings Storage** | Local (`chrome.storage`) for user preferences, exclusion list |

---

## 6. AI Model Requirements

### 6.1 Model Type
Context-based QA/explanation model — **general-purpose**, since it must handle arbitrary text from any website (not a fixed knowledge base like the embedded-widget version).

### 6.2 Approach
| Approach | Description |
|---|---|
| **Prompted LLM (primary)** | General LLM explains hovered text using surrounding page context as grounding |
| **Web-augmented lookup (optional, v2)** | For proper nouns, niche jargon, or current events, optionally trigger a web search to enrich the explanation |
| **No fine-tuning needed for v1** | Domain is too broad (any website) for fine-tuning to be practical early on |

### 6.3 Prompt Design (example)
```
System: You are a browser-overlay reading assistant. The user hovered over 
text on a webpage. Explain it clearly and concisely using the surrounding 
context. If the text is ambiguous out of context, note the ambiguity.

Hovered text: "{selected_text}"
Surrounding context: "{nearby_text}"
Page title: "{page_title}"
Page URL domain: "{domain}"
```

### 6.4 Guardrails
- Must not fetch or process content behind login walls/paywalls beyond what's rendered in the DOM
- Must not act on sensitive categories of pages (banking, health portals) unless explicitly allowed by user
- Should decline to explain content that violates the extension's own content policy (e.g., helping bypass security)

---

## 7. UX Requirements

- Overlay must **never break site layout** — must use Shadow DOM / iframe isolation
- Response latency target: **under 2 seconds** to start streaming explanation
- Draggable/repositionable chatbox; remembers last position per user
- Keyboard accessible; screen-reader friendly overlay
- Dark/light mode matching browser theme
- Works across scrolling, SPA route changes (e.g., React/Vue sites), and dynamically loaded content
- Graceful degradation: if a site blocks content scripts (rare, e.g., strict CSP), show a subtle "unavailable on this page" indicator instead of failing silently

---

## 8. Success Metrics (KPIs)

| Metric | Target (initial) |
|---|---|
| Weekly active users (extension) | Track post-launch |
| Avg. hovers/explanations per active session | ≥ 3 |
| Follow-up question rate | ≥ 30% of explanations get a follow-up |
| Extension uninstall rate | < 15% within first week |
| User satisfaction (thumbs up/down on explanations) | ≥ 80% positive |
| Store rating (Chrome Web Store) | ≥ 4.3★ |

---

## 9. Risks & Considerations

| Risk | Mitigation |
|---|---|
| Privacy concerns (reading arbitrary page content) | Minimal data capture, clear consent UI, site exclusion list, no full-page storage |
| Performance overhead on every page | Lightweight content script, lazy-load overlay UI only on first hover |
| Breaking site layouts/CSS conflicts | Shadow DOM isolation, extensive cross-site testing |
| Manifest V3 restrictions (Chrome) | Design around service worker limitations, no persistent background page |
| Abuse (bypassing paywalls, scraping restricted content) | Explicit policy + technical limits: only DOM-visible text, no network-level scraping |
| LLM cost at scale (every hover = API call) | Debounce triggers, cache repeated explanations per domain+text hash, tiered free/paid usage |
| App store review rejection | Follow Chrome Web Store / Firefox policies closely, especially around remote code and data usage disclosure |

---

## 10. Milestones / Rollout Plan

| Phase | Scope | Timeline (indicative) |
|---|---|---|
| **Phase 1 – MVP Extension** | Chrome extension, hover trigger, basic overlay chatbox, LLM explanation (no history/follow-up memory) | 4–5 weeks |
| **Phase 2 – Conversational Context** | Follow-up Q&A, per-hover conversation memory, settings panel | 3–4 weeks |
| **Phase 3 – Privacy & Controls** | Site exclusion list, consent flow, local settings storage, caching | 2–3 weeks |
| **Phase 4 – Multi-browser & Polish** | Firefox/Edge support, dark mode, accessibility audit, performance tuning | 3–4 weeks |
| **Phase 5 – Store Launch** | Chrome Web Store submission, marketing site, onboarding flow | 2 weeks |

---

## 11. Permissions & Compliance Notes
- Chrome extension manifest will need: `activeTab`, `scripting`, `storage`; avoid broad `<all_urls>` host permission if possible (request per-site activation instead, better for store approval and user trust)
- Must publish a clear privacy policy (what's captured, sent to backend, retained)
- Should comply with GDPR/CCPA if capturing any user data tied to identity

---

## 12. Open Questions
- Should this be free, freemium (limited hovers/day), or subscription-based?
- Should it support PDF viewers and browser-native reader mode, or only standard HTML pages?
- Do you want cross-device sync of settings/history (requires account/login), or fully local/anonymous?
- Multi-language explanation support needed at launch?

---

*This PRD supersedes the earlier "embedded website widget" version — scope has shifted from a site-owner-installed widget to a user-installed browser extension that overlays on any site.*
