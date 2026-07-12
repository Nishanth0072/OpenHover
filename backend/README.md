# 🧠 Open-Brain Backend

Unified, secure backend service for Android and Windows AI client applications. Built with **FastAPI**, **SQLAlchemy** (PostgreSQL), and **Redis**.

This service implements secure registration with OTP email validation, two-factor authentication (MFA) via email, a sliding-window rate limiter, and a single-session access token blacklist using Redis.

---

## 📖 API Documentation Guides

We have created comprehensive integration guides and API documentations for developers building frontend clients:

*   **[Core API Reference](file:///c:/Users/mithun/backend%20openbrain/API_DOCUMENTATION.md)** — Exhaustive list of all endpoints, request/response models, and error statuses.
*   **[Android Integration Guide](file:///c:/Users/mithun/backend%20openbrain/ANDROID_FRONTEND_API_DOC.md)** — Detailed Android frontend guide with OkHttp/Retrofit examples, token storage tips, and flow diagrams.
*   **[Windows Integration Guide](file:///c:/Users/mithun/backend%20openbrain/WINDOWS_FRONTEND_API_DOC.md)** — Detailed Windows desktop integration guide using C# HttpClient, session management, and SSE stream parsing.

---

## 🚀 Getting Started

### Prerequisites
*   [Docker Desktop](https://www.docker.com/products/docker-desktop/)
*   Python 3.12+ (if running tests locally)

### Running the Services (Docker Compose)
The simplest way to start the backend, database, and Redis cache is via Docker Compose:

```bash
# Build and launch all containers
docker compose up --build -d
```

This starts:
1.  **FastAPI Application** on port `8000` (mapped to `localhost:8000`)
2.  **PostgreSQL 16** on port `5432`
3.  **Redis 7** on port `6379`
4.  **Nginx Reverse Proxy** on port `80`

### Database Migrations
Always run database migrations to keep your database schema up to date:

```bash
docker exec -e PYTHONPATH=/app openbrain-api alembic upgrade head
```

---

## 🛠️ Developer Tools & CLI Client

### 1. Interactive API Docs
Once the server is running, you can access the interactive documentation pages directly:
*   **Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)
*   **ReDoc:** [http://localhost:8000/redoc](http://localhost:8000/redoc)

### 2. Command Line Interface (CLI) Client
A persistent, session-aware CLI terminal is included for testing registration, logging in with MFA, and chatting with AI models in a live streaming REPL:

```bash
# Install HTTPX requirement
pip install httpx

# Launch the interactive client
python cli.py
```

---

## 🧪 Testing the API
We have provided a fully automated endpoint validation test suite that simulates user registration, OTP retrieval, login MFA verification, and profile fetching:

```bash
# Run the automated batch test
.\test_endpoints.bat
```
