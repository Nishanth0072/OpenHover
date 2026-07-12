# Tech Stack — HoverMind Browser Extension

## 1. Browser Extension (Client)

| Layer | Technology | Notes |
|---|---|---|
| Extension framework | **Manifest V3** (Chrome/Edge), WebExtensions API (Firefox) | Required for Chrome Web Store; Firefox supports MV3 too |
| Content script | **TypeScript** | Injected into every page to detect hover/select + extract context |
| Overlay UI | **React + Shadow DOM** | Shadow DOM isolates styling from host page CSS |
| Styling | **Tailwind CSS (scoped/shadow-safe build)** or CSS-in-JS (vanilla-extract / styled-components) | Must not leak into or be affected by host page styles |
| Build tool | **Vite** with `@crxjs/vite-plugin` (or Plasmo framework) | Plasmo is purpose-built for browser extensions, handles MV3 boilerplate well |
| Background logic | **Service Worker (MV3)** in TypeScript | Handles API calls, cross-tab state, auth token storage |
| Local storage | `chrome.storage.local` / `chrome.storage.sync` | Settings, site-exclusion list, cached explanations |
| Extension popup (settings) | **React** (small SPA) | On/off toggle, preferences, exclusion list |

## 2. Backend API

| Layer | Technology | Notes |
|---|---|---|
| API framework | **Node.js + Express/Fastify** or **Python FastAPI** | FastAPI if team prefers Python for LLM tooling ecosystem |
| Auth | **JWT + OAuth (Google/GitHub sign-in)** or anonymous device-based tokens for v1 | Depends on whether accounts are required |
| Rate limiting / caching | **Redis** | Cache explanations by hash(domain + text) to cut LLM costs; rate-limit per user/IP |
| API Gateway | **Cloudflare Workers** or **AWS API Gateway** | Edge-deployed for low latency close to users |
| Queue (optional, for async enrichment) | **AWS SQS / Cloudflare Queues** | If adding web-search enrichment step later |

## 3. AI / LLM Layer

| Component | Technology | Notes |
|---|---|---|
| Primary LLM | **Z.ai — GLM-4.7 Flash / GLM-4.5 Flash (free tier)** | OpenAI-compatible endpoint; $0 cost, good enough for concise text explanations |
| Fallback/escalation LLM (optional) | **GLM-4.5-Air** ($0.20/$1.10 per MTok) | Use only if Flash confidence/quality is too low for a specific query, or free-tier rate limit is hit |
| Prompt orchestration | **Direct API calls** (no heavy framework needed for v1); consider **LangChain/LlamaIndex** only if RAG grows complex | Keep it simple initially |
| Optional web enrichment (v2) | **Bing/Google Search API** or a free search API | For niche terms/current events not resolvable from page context alone |
| Streaming responses | **Server-Sent Events (SSE)** from backend to extension | For "start typing" feel under 2s |

## 4. Data & Storage

| Purpose | Technology |
|---|---|
| User settings/preferences (if account-based) | **PostgreSQL** (via Supabase or managed RDS) |
| Explanation cache | **Redis** (short-medium TTL, keyed by domain+text hash) |
| Analytics events | **PostHog** (self-hostable, privacy-friendly) or **Amplitude** |
| Session/conversation history (opt-in only) | **PostgreSQL** or **DynamoDB** (if fully serverless) |

## 5. Infrastructure & DevOps

| Layer | Technology |
|---|---|
| Hosting (backend) | **Cloudflare Workers** (edge, low latency) or **AWS (ECS/Fargate)** / **Render/Fly.io** for simpler ops |
| CI/CD | **GitHub Actions** — lint, test, build extension bundle, auto-publish to stores via `web-ext` / Chrome Web Store API |
| Monitoring/Logging | **Sentry** (extension + backend error tracking), **Datadog/Grafana** (backend metrics) |
| Secrets management | **Doppler** or cloud-native secrets manager (AWS Secrets Manager) |

## 6. Testing

| Type | Technology |
|---|---|
| Unit tests | **Vitest / Jest** |
| E2E extension testing | **Playwright** (supports extension testing in Chromium) |
| API testing | **Supertest** (Node) or **pytest** (Python) |

## 7. Suggested Stack Summary (Opinionated Default)

```
Extension:   Plasmo Framework (React + TypeScript) + Tailwind (shadow-scoped)
Backend:     Node.js (Fastify) + TypeScript
LLM:         Z.ai GLM-4.7 Flash / GLM-4.5 Flash (free) → GLM-4.5-Air (paid fallback)
Cache/Rate-limit: Redis
Database:    PostgreSQL (Supabase, for easy auth + DB combo)
Hosting:     Cloudflare Workers (API edge) + Supabase (DB/auth)
Analytics:   PostHog
CI/CD:       GitHub Actions
Monitoring:  Sentry
```

This combination minimizes infra overhead for a small team, keeps latency low (edge-deployed API), and avoids over-engineering the LLM layer before you have real usage data to justify RAG or fine-tuning.

## 8. Why This Stack (Rationale)

- **Plasmo** over raw Manifest V3 boilerplate: dramatically cuts extension dev time, handles MV3 quirks, hot-reload for content scripts.
- **Shadow DOM + scoped Tailwind**: only reliable way to guarantee the overlay doesn't break on arbitrary third-party sites.
- **Z.ai GLM Flash models (free) for v1**: your use case (short context + text in, concise explanation out) doesn't need frontier-model reasoning. Free tier removes the biggest cost risk of a hover-triggered feature (every hover = a potential call), and the API is OpenAI-compatible so it's a drop-in swap later if quality needs upgrading.
- **No LangChain for v1**: this use case doesn't need a heavy orchestration framework yet — adding one early adds complexity without benefit.
- **Redis caching**: hover-triggered LLM calls can get expensive fast at scale; caching identical (domain, text) pairs cuts cost significantly.
- **Cloudflare Workers**: edge deployment matters here since latency directly affects UX (target <2s response).
- **Supabase**: bundles Postgres + auth + storage, reducing infra pieces to manage for a lean team.

## 9. Alternatives to Consider

| Decision | Alternative | Trade-off |
|---|---|---|
| Plasmo | Raw Vite + `@crxjs/vite-plugin` | More control, more setup work |
| Node/Fastify | Python FastAPI | Better if team wants tighter LLM/data-science tooling later |
| Cloudflare Workers | AWS Lambda / traditional server (ECS) | More AWS-native, but higher latency and cold-start considerations |
| PostHog | Amplitude/Mixpanel | PostHog is self-hostable for privacy-sensitive product; others are more polished SaaS |
| Z.ai GLM Flash (free) | Groq (free tier, Llama/Mixtral models, very fast inference) | Groq has a generous free tier and extremely low latency; weaker at nuanced text explanation than GLM |
| Z.ai GLM Flash (free) | Google Gemini API (free tier, Gemini Flash models) | Solid free tier and quality; Google account/project setup required, rate limits apply |
| Z.ai GLM Flash (free) | OpenRouter free-tier models (aggregates multiple free open models) | One integration, many free models to test/swap between; reliability varies by underlying model |

**Note on datasets:** since you mentioned you're building a dataset alongside this, keep the model choice decoupled from data collection — log the raw `{selected_text, context, model_response}` triples regardless of which LLM generates them, so you can swap providers later without losing training data compatibility.
