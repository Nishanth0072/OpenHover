# PRD: Unified Backend for Android & Windows AI Client Apps

**Product:** Open-Brain Backend Service
**Owner:** Open-Brain Team
**Version:** 1.0
**Date:** July 2026

---

## 1. Overview

A centralized backend service that both the Android app and the Windows app connect to over HTTP/HTTPS. The backend authenticates users, validates requests, and acts as a secure proxy/broker between client apps and one or more AI provider APIs (e.g. Claude, OpenAI, Ollama Cloud). It is exposed to the internet safely via Cloudflare Tunnel, sits behind Nginx as a reverse proxy, uses Redis for low-latency caching/session/rate-limit data, and persists durable data in PostgreSQL. All endpoints are documented (OpenAPI/Swagger) so frontend developers (Android/Kotlin, Windows/C#/Electron) can integrate without back-and-forth.

## 2. Goals

- One backend, two clients (Android, Windows) — shared contract, no duplicated logic.
- Secure user auth (signup/login/session) with proper validation.
- Safe AI-provider proxying: clients never hold provider API keys directly (or, if BYOK, keys are validated/stored securely).
- Low-latency repeated calls via Redis caching (sessions, rate limits, provider responses where cacheable).
- Public accessibility without exposing home/dev server IP — via Cloudflare Tunnel.
- Fully documented REST API (OpenAPI spec + Swagger UI + Postman collection) so client devs can build against it immediately.

## 3. Non-Goals

- Building the AI models themselves (backend only orchestrates calls to providers).
- Building the Android/Windows UI (covered in separate app-side PRDs — this is backend-only).

## 4. Users & Use Cases

| User | Use Case |
|---|---|
| Android app user | Sign up/login, send AI prompts, get streamed/complete responses, manage chat history |
| Windows app user | Same as above, from desktop client |
| Frontend developer (you/team) | Needs a documented, stable API to integrate against |
| Admin (you) | Needs to monitor usage, manage rate limits, rotate provider keys |

## 5. High-Level Architecture

```
┌─────────────┐     ┌─────────────┐
│ Android App │     │ Windows App │
└──────┬──────┘     └──────┬──────┘
       │  HTTPS (REST/JSON, SSE for streaming)
       └───────────┬───────┘
                    ▼
          ┌───────────────────┐
          │  Cloudflare Tunnel │  (public HTTPS endpoint, no exposed home IP)
          └─────────┬─────────┘
                    ▼
          ┌───────────────────┐
          │      Nginx        │  (reverse proxy, TLS termination, rate limiting,
          │  (reverse proxy)  │   gzip, request routing)
          └─────────┬─────────┘
                    ▼
          ┌───────────────────┐
          │     FastAPI       │  (REST API, auth, validation, business logic,
          │   (Uvicorn/       │   AI provider orchestration)
          │    Gunicorn)      │
          └───┬───────────┬───┘
              │           │
              ▼           ▼
        ┌──────────┐  ┌─────────┐
        │PostgreSQL│  │  Redis  │  (sessions, rate-limit counters,
        │ (users,  │  │ (cache, │   short-lived AI response cache,
        │  chats,  │  │ queues) │   pub/sub for streaming if needed)
        │  keys)   │  └─────────┘
        └──────────┘
              │
              ▼
     ┌──────────────────┐
     │  AI Provider APIs  │  (Claude API, OpenAI, Ollama Cloud, etc.)
     └──────────────────┘
```

## 6. Functional Requirements

### 6.1 User Authentication & Validation
- Register (email + password, or email + OTP) with strong validation (email format, password strength, duplicate check).
- Login with JWT (access token + refresh token pattern).
- Token refresh endpoint.
- Logout (refresh token revocation, stored/blacklisted in Redis).
- Password hashing with bcrypt/argon2 — never store plaintext.
- Rate-limit login attempts (Redis-backed) to block brute force.
- Optional: email verification, forgot/reset password flow.
- Input validation via Pydantic models on every endpoint (reject malformed/oversized payloads before they touch business logic).

### 6.2 AI Proxy Layer
- `POST /ai/chat` — accepts a prompt + conversation context, forwards to selected AI provider, returns response (supports streaming via Server-Sent Events or chunked responses for both Android and Windows clients).
- Provider abstraction layer: single internal interface, multiple provider adapters (Claude, OpenAI, Ollama) selected by config or user preference (BYOK — Bring Your Own Key — support, as per Open-Brain's existing architecture).
- Redis caches: rate-limit counters per user, idempotency keys for retried requests, optionally short-TTL response caching for identical prompts.
- Per-user and per-plan rate limiting (requests/minute, tokens/day).

### 6.3 Chat/Session Data
- Store conversation history in PostgreSQL (linked to user_id).
- Endpoints to list, fetch, delete conversations.
- Pagination for chat history.

### 6.4 API Documentation
- FastAPI auto-generates OpenAPI 3.1 schema at `/openapi.json`.
- Swagger UI at `/docs`, ReDoc at `/redoc` — both must be reachable so Android/Windows devs can browse and test live.
- Exported Postman collection generated from the OpenAPI schema for teammates who prefer Postman.
- Every endpoint must have: summary, description, request/response Pydantic schemas with examples, and documented error codes.

### 6.5 Infra & Networking
- Nginx as reverse proxy in front of Uvicorn/Gunicorn workers — handles TLS (if not already terminated at Cloudflare), gzip compression, basic rate limiting, and routes `/api/*` to FastAPI.
- Cloudflare Tunnel (`cloudflared`) connects the local/self-hosted backend to a public HTTPS hostname without opening router ports — this is what both the Android and Windows apps hit from the outside world.
- CORS configured to allow the specific client origins/schemes used by the Windows app (if it's a web-based shell) and standard mobile HTTP client headers for Android.

## 7. Non-Functional Requirements

| Category | Requirement |
|---|---|
| Security | HTTPS only (enforced end-to-end), JWT with short-lived access tokens, refresh token rotation, hashed passwords, input validation on all endpoints, secrets in `.env`/vault (never committed) |
| Performance | Redis caching for hot paths, async FastAPI endpoints, connection pooling for PostgreSQL (e.g. asyncpg + SQLAlchemy async) |
| Scalability | Stateless FastAPI workers (scale horizontally behind Nginx), Redis/PostgreSQL as shared state |
| Observability | Structured logging, request IDs, basic metrics (request count, latency, error rate) |
| Availability | Cloudflare Tunnel gives resilience against direct network exposure issues; health-check endpoint `/health` |
| Documentation | Auto-generated OpenAPI spec kept in sync with code (single source of truth) |

## 8. Tech Stack

| Layer | Technology | Notes |
|---|---|---|
| Client → Edge | **Cloudflare Tunnel** (`cloudflared`) | Exposes backend publicly over HTTPS without port-forwarding; gives a stable public hostname |
| Reverse Proxy | **Nginx** | TLS termination (or pass-through if Cloudflare handles it), load balancing across Uvicorn workers, gzip, basic rate limiting |
| API Framework | **FastAPI** (Python 3.12+) | Async REST API, automatic OpenAPI/Swagger docs, Pydantic v2 validation |
| ASGI Server | **Uvicorn** (managed by **Gunicorn** with `uvicorn.workers.UvicornWorker`) | Production process manager for multiple workers |
| Database | **PostgreSQL 16** | Users, chat history, API key metadata, audit logs |
| ORM / DB Access | **SQLAlchemy 2.0 (async)** + **Alembic** | Migrations + async ORM |
| Cache / Fast Access | **Redis 7** | Sessions, rate-limit counters, refresh-token blacklist, short-TTL AI response cache, pub/sub for streaming fan-out |
| Auth | **JWT** (`python-jose` or `pyjwt`) + **passlib[bcrypt]** or **argon2-cffi** | Access + refresh token pattern |
| Validation | **Pydantic v2** | Request/response schema validation, built into FastAPI |
| AI Provider Integration | **httpx (async)** clients per provider (Claude API, OpenAI, Ollama Cloud) | Provider-adapter pattern for BYOK multi-provider routing |
| API Docs | **FastAPI built-in OpenAPI**, Swagger UI (`/docs`), ReDoc (`/redoc`) | Postman collection exported from OpenAPI JSON |
| Background Tasks | **FastAPI BackgroundTasks** or **Celery + Redis** (if heavier async jobs needed) | For things like usage logging, async email |
| Containerization | **Docker + Docker Compose** | `fastapi`, `postgres`, `redis`, `nginx` services |
| Secrets Management | `.env` + `python-dotenv` (dev), vault/1Password/Doppler (prod) | Never commit secrets |
| Logging/Monitoring | `loguru` or standard `logging` + optional **Prometheus + Grafana** later | Structured JSON logs |

## 9. Core API Surface (initial cut)

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/auth/register` | Create user account |
| POST | `/auth/login` | Authenticate, return access + refresh JWT |
| POST | `/auth/refresh` | Exchange refresh token for new access token |
| POST | `/auth/logout` | Revoke refresh token |
| GET | `/users/me` | Get current authenticated user profile |
| GET | `/ai/characters` | List available AI characters |
| POST | `/ai/chat` | Send prompt to AI provider, get response (supports streaming) |
| GET | `/chats` | List user's conversations |
| GET | `/chats/{id}` | Get a conversation's full history |
| DELETE | `/chats/{id}` | Delete a conversation |
| GET | `/health` | Liveness/readiness check |
| GET | `/docs` | Swagger UI |
| GET | `/openapi.json` | Raw OpenAPI schema |

## 10. Data Model (initial)

**users**: `id, email, password_hash, created_at, is_verified, plan`
**refresh_tokens**: `id, user_id, token_hash, expires_at, revoked`
**conversations**: `id, user_id, title, created_at, updated_at`
**messages**: `id, conversation_id, role (user/assistant), content, provider_used, token_count, created_at`
**provider_keys** (if BYOK): `id, user_id, provider_name, encrypted_key, created_at`

## 11. Security Checklist

- [ ] All traffic HTTPS-only (enforced via Nginx redirect + Cloudflare)
- [ ] Passwords hashed with bcrypt/argon2, never logged
- [ ] JWT secrets rotated, short access-token TTL (e.g. 15 min), refresh TTL (e.g. 7–30 days)
- [ ] Refresh tokens revocable (stored/checked in Redis or DB)
- [ ] Pydantic validation on every request body/query param
- [ ] Rate limiting per user/IP (Nginx + Redis-backed counters)
- [ ] BYOK provider keys encrypted at rest (e.g. Fernet/AES) if stored server-side
- [ ] CORS restricted to known client origins
- [ ] SQL injection not possible (parameterized via SQLAlchemy ORM)
- [ ] Dependency/CVE scanning in CI

## 12. Milestones

| Milestone | Deliverable |
|---|---|
| M1 | FastAPI skeleton + PostgreSQL + Alembic migrations + `/health` |
| M2 | Auth flow (register/login/refresh/logout) with JWT + Redis blacklist |
| M3 | AI proxy layer (single provider first, e.g. Claude) + chat history persistence |
| M4 | Multi-provider adapter pattern (BYOK support) + Redis caching/rate limits |
| M5 | Nginx reverse proxy + Cloudflare Tunnel setup for public access |
| M6 | Full OpenAPI docs polish + Postman collection export + handoff to Android/Windows devs |

## 13. Open Questions

- Will provider API keys be BYOK (stored per-user, encrypted) or centrally managed by the backend?
- Does the Windows client need WebSocket-based streaming, or is SSE/chunked HTTP sufficient?
- Any offline/local-first requirement for the Windows app that the backend needs to account for (e.g. sync on reconnect)?