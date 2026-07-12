# 🧠 OpenHover — AI Reading Companion

A browser extension that overlays an AI chatbox on **any website**, instantly explaining whatever text you hover over.

![Manifest V3](https://img.shields.io/badge/Manifest-V3-blueviolet)
![Plasmo](https://img.shields.io/badge/Built%20with-Plasmo-8b5cf6)
![TypeScript](https://img.shields.io/badge/TypeScript-5.3-blue)
![React](https://img.shields.io/badge/React-18-61dafb)

## Features

- **Hover to Explain** — Hover over any text on any webpage for ~600ms to get an AI-generated explanation
- **Floating Chatbox** — Draggable, minimizable overlay panel with glassmorphism design
- **Streaming Responses** — Real-time typing feel via Server-Sent Events
- **Follow-up Questions** — Suggested follow-ups appear after each explanation
- **Site Exclusions** — Block specific domains (banking, email, etc.)
- **Configurable** — Adjust hover delay, trigger mode, response length
- **Shadow DOM Isolation** — Overlay never breaks host page CSS
- **Privacy First** — No data stored without consent, minimal context sent

## Supported Browsers

| Browser | Status |
|---------|--------|
| Chrome  | ✅ Supported |
| Brave   | ✅ Supported |
| Edge    | ✅ Supported |
| Firefox | ✅ Supported (MV3) |

## Project Structure

```
openhover/                  ← Browser extension (Plasmo + React + TypeScript)
├── background.ts           ← MV3 service worker
├── popup.tsx / popup.css   ← Settings panel
├── contents/
│   ├── openhover.tsx       ← Content script (hover detection + overlay)
│   └── openhover.css       ← Chatbox styles (glassmorphism dark theme)
├── components/
│   ├── ChatBox.tsx         ← Floating draggable chatbox
│   ├── ExplanationCard.tsx ← AI response with markdown + feedback
│   ├── LoadingState.tsx    ← Animated loading dots
│   └── MinimizedBubble.tsx ← Collapsed bubble
├── lib/
│   ├── api.ts              ← SSE streaming API client
│   ├── constants.ts        ← Defaults, ignored elements
│   ├── context.ts          ← DOM text extraction
│   └── storage.ts          ← chrome.storage wrapper
└── build/
    ├── chrome-mv3-dev/     ← Dev build (load in Chrome/Brave/Edge)
    └── chrome-mv3-prod/    ← Production build

backend/                    ← API server (Node.js + Fastify)
├── src/
│   ├── server.ts           ← Fastify entry (CORS, rate-limit)
│   ├── routes/explain.ts   ← POST /api/explain (SSE streaming)
│   └── services/
│       ├── llm.ts          ← Z.ai GLM-4.5-Flash integration
│       └── cache.ts        ← In-memory LRU cache
└── .env                    ← API key config
```

## Getting Started

### Prerequisites

- Node.js 18+
- A Z.ai (Zhipu AI) API key — [get one here](https://open.bigmodel.cn/)

### 1. Start the Backend

```bash
cd backend
cp .env.example .env        # Add your ZHIPU_API_KEY
npm install
npm run dev                 # Starts on http://localhost:3001
```

### 2. Start the Extension (Development)

```bash
cd openhover
npm install
npm run dev                 # Builds to build/chrome-mv3-dev/
```

### 3. Load in Browser

**Chrome / Brave / Edge:**
1. Navigate to `chrome://extensions/` (or `brave://extensions/` / `edge://extensions/`)
2. Enable **Developer mode**
3. Click **"Load unpacked"**
4. Select `openhover/build/chrome-mv3-dev`

**Firefox:**
```bash
npm run dev:firefox         # Builds to build/firefox-mv3-dev/
```
Then load via `about:debugging` → "Load Temporary Add-on"

### 4. Use It

1. Visit any webpage
2. Hover over text for ~600ms
3. The OpenHover chatbox appears with an AI explanation
4. Drag to reposition, minimize, or close

## Build Scripts

| Command | Description |
|---------|-------------|
| `npm run dev` | Dev mode with hot reload (Chrome/Brave/Edge) |
| `npm run dev:firefox` | Dev mode for Firefox |
| `npm run build` | Production build (Chrome/Brave/Edge) |
| `npm run build:firefox` | Production build for Firefox |
| `npm run build:all` | Build for all browsers |
| `npm run package` | Package for Chrome Web Store |

## Extension Settings

Click the OpenHover icon in the toolbar to access:

- **Enable/Disable** — Global toggle
- **Trigger Mode** — Hover / Select text / Click icon
- **Hover Delay** — 200ms to 1500ms slider
- **Response Length** — Concise or Detailed
- **Site Exclusions** — Block domains like `bank.com`

## Tech Stack

- **Extension**: [Plasmo Framework](https://plasmo.com/) + React + TypeScript
- **UI**: Shadow DOM with scoped CSS (glassmorphism dark theme)
- **Backend**: Node.js + Fastify + TypeScript
- **LLM**: Z.ai GLM-4.5-Flash (free tier, OpenAI-compatible)
- **Caching**: In-memory LRU (Redis-ready)
- **Streaming**: Server-Sent Events (SSE)

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/explain` | Stream AI explanation for hovered text |
| `GET`  | `/api/health` | Health check + cache stats |

## License

MIT
