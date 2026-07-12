# Open-Brain — Project Architecture & Directory Structure

Welcome to the **Open-Brain** backend and interactive CLI codebase. This document outlines the purpose of each file and folder in the repository to make it easy to understand and navigate.

---

## 📁 Repository Overview

Here is the directory tree of the project:

```text
openbrain/
├── .env                          # Local environment secrets and configuration
├── .env.example                  # Template for environment variables
├── .gitignore                    # Git file exclusion rules
├── ABOUT.md                      # [THIS FILE] Project structure guide
├── Dockerfile                    # Containerization setup for the FastAPI app
├── alembic.ini                   # Alembic database migration config
├── chat_cli.py                   # Interactive AI Chat CLI tool
├── docker-compose.yml            # Multi-container orchestration (App, DB, Redis, Nginx)
├── requirements.txt              # Backend dependencies
├── test_endpoints.bat            # Script to run endpoint integration tests
├── prd.md                        # Product Requirements Document
├── api_and_session_plan.md       # API design & session management plan
├── edge_cases_plan.md            # Boundary handling plan
├── implementation_plan.md        # Technical implementation & roadmap
│
├── alembic/                      # Database migrations folder
│   ├── env.py                    # Alembic migration configuration environment
│   ├── script.py.mako            # Migration template file
│   └── versions/                 # History of SQL schema revisions
│
├── nginx/                        # Proxy server configurations
│   └── nginx.conf                # Nginx proxy mapping port 80 to FastAPI backend
│
└── app/                          # Core FastAPI backend source code
    ├── __init__.py               # App module entry point
    ├── config.py                 # Pydantic Settings settings manager
    ├── database.py               # Database engine, session, and ORM Base setup
    ├── dependencies.py           # FastAPI endpoint dependencies (Auth, DB, Redis, Rate Limiter)
    ├── main.py                   # App startup, routing setup, middleware mount
    ├── redis.py                  # Redis connection and utility wrapper
    │
    ├── middleware/               # HTTP Middlewares
    │   ├── __init__.py           # Package initializer
    │   └── rate_limiter.py       # Rate-limiting middleware / logic
    │
    ├── models/                   # SQLAlchemy Database Models (Schema)
    │   ├── __init__.py           # Imports models to expose them to Alembic
    │   ├── user.py               # User account model
    │   ├── refresh_token.py      # Refresh token model for authentication session persistence
    │   ├── conversation.py       # Chat conversation metadata model
    │   └── message.py            # Individual chat message model
    │
    ├── providers/                # AI LLM Provider Integrations
    │   ├── __init__.py           # Package initializer
    │   ├── base.py               # Abstract Base Class defining LLM provider interfaces
    │   ├── ollama.py             # Ollama local/self-hosted model provider
    │   ├── openai_provider.py    # OpenAI (GPT-4o, etc.) streaming provider
    │   └── claude.py             # Anthropic Claude streaming provider
    │
    ├── routers/                  # API Endpoints & Routes
    │   ├── __init__.py           # Package initializer
    │   ├── ai.py                 # Chat prompt & LLM stream endpoints
    │   ├── auth.py               # Registration, Login, Token Refresh endpoints
    │   ├── chats.py              # Conversation CRUD & message history endpoints
    │   └── users.py              # User profiles & user state endpoints
    │
    ├── schemas/                  # Pydantic Schemas for validation
    │   ├── __init__.py           # Package initializer
    │   ├── ai.py                 # Chat request/response payloads
    │   ├── auth.py               # Auth login/signup requests, JWT tokens
    │   └── chat.py               # Conversation & message display models
    │
    └── services/                 # Business Logic Layer (Services)
        ├── __init__.py           # Package initializer
        ├── ai_service.py         # Selects, validates, and coordinates LLM providers
        ├── auth_service.py       # Token generation, user password hashing, JWT validations
        └── chat_service.py       # Database operations for conversations and message persistence
```

---

## 🔍 Detailed Component Guide

### 🚀 Application Root Files

* **[.env](file:///.env)**: Houses secrets, database credentials, external API keys (e.g. OpenAI/Anthropic), JWT secret keys, and runtime configurations. *Do not check this file into Git.*
* **[.env.example](file:///.env.example)**: A placeholder/template outlining what environment parameters are required to run the service.
* **[Dockerfile](file:///Dockerfile)**: Describes the build context, dependency installation, and startup command for containerizing the FastAPI application.
* **[docker-compose.yml](file:///docker-compose.yml)**: Sets up the full development stack including the FastAPI app (`api`), PostgreSQL 16 database (`postgres`), Redis caching service (`redis`), and Nginx reverse proxy (`nginx`).
* **[chat_cli.py](file:///chat_cli.py)**: An interactive command-line application that allows developers or end-users to register, log in, view chat histories, create new threads, and stream AI responses directly in the console.
* **[requirements.txt](file:///requirements.txt)**: Contains the exact Python package dependencies (FastAPI, SQLAlchemy, asyncpg, passlib, PyJWT, httpx, etc.) required for the application.
* **[test_endpoints.bat](file:///test_endpoints.bat)**: A Windows Batch script containing a suite of cURL integration commands to test backend authentication, user signup, API endpoints, and chat operations.
* **Documentation (`*.md`)**:
  * **[prd.md](file:///prd.md)**: Product Requirement Document defining requirements, scope, features, and architecture.
  * **Plans**: Contains technical proposals and review files for system components ([api_and_session_plan.md](file:///api_and_session_plan.md), [edge_cases_plan.md](file:///edge_cases_plan.md), [implementation_plan.md](file:///implementation_plan.md)).

---

### 📦 Major Subdirectories

#### 🔄 `alembic/` (Database Migrations)
This directory is managed by Alembic and generates step-by-step SQL migrations for changes to the database schemas.
* **[env.py](file:///alembic/env.py)**: Connects SQLAlchemy database engine settings and model metadata to execute schema updates.
* **[versions/](file:///alembic/versions)**: Contains individual revision scripts (such as `2026_07_04_1fff792d0853_initial_revision.py`) tracking incremental changes to the database schemas.

#### 🌐 `nginx/` (Reverse Proxy)
* **[nginx.conf](file:///nginx/nginx.conf)**: Configures Nginx to forward port 80 traffic (and reverse proxy requests) safely to the backend FastAPI application.

#### 🛠️ `app/` (FastAPI Application Core)
This is the heart of the server-side code:

* **[config.py](file:///app/config.py)**: Loads configuration parameters from the environment and maps them to a secure Pydantic model (`Settings`).
* **[database.py](file:///app/database.py)**: Configures the asynchronous engine using SQLAlchemy, sets up session maker objects, and exposes the `Base` class for ORM mapping.
* **[dependencies.py](file:///app/dependencies.py)**: Expresses shareable FastAPI dependencies, such as fetching current user sessions, retrieving database transactions, checking Redis nodes, and throttling requests.
* **[main.py](file:///app/main.py)**: Bootstraps the application, mounts middlewares, adds cross-origin resource sharing (CORS), and sets up routing.
* **[redis.py](file:///app/redis.py)**: Defines connections and caching client operations using the Redis server.

---

### 📂 Inside `app/` Subdirectories

#### 🛡️ `app/middleware/`
* **[rate_limiter.py](file:///app/middleware/rate_limiter.py)**: Holds backend middleware or custom logic that throttles requests based on IP addresses or logged-in accounts to avoid abuse.

#### 🗄️ `app/models/` (SQLAlchemy Models)
* **[user.py](file:///app/models/user.py)**: Represents the DB structure of user accounts, storage of hashed passwords, verified status, tier plans, and token versions.
* **[refresh_token.py](file:///app/models/refresh_token.py)**: Tracks active, expired, and revoked refresh tokens for managing user sessions.
* **[conversation.py](file:///app/models/conversation.py)**: Contains chat metadata, including the title and creation timestamp for specific user threads.
* **[message.py](file:///app/models/message.py)**: Represents individual prompt-response pairs within conversations, keeping track of content, role (e.g. system, user, assistant), and token counts.

#### 🤖 `app/providers/` (AI Integrations)
This layer acts as an abstraction for external language model APIs:
* **[base.py](file:///app/providers/base.py)**: Outlines the contract/base interface all provider classes must satisfy.
* **[openai_provider.py](file:///app/providers/openai_provider.py)**: Integrates OpenAI's Chat Completion API with streaming capabilities.
* **[claude.py](file:///app/providers/claude.py)**: Integrates Anthropic's Claude API with streaming capabilities.
* **[ollama.py](file:///app/providers/ollama.py)**: Handles local LLM interactions using a self-hosted Ollama endpoint.

#### 🛣️ `app/routers/` (FastAPI Routes)
* **[auth.py](file:///app/routers/auth.py)**: Endpoints for signing up, signing in, logging out, and issuing fresh access tokens.
* **[users.py](file:///app/routers/users.py)**: Endpoints for user profile inquiries and user tier modifications.
* **[chats.py](file:///app/routers/chats.py)**: Endpoints for creating conversations, listing user conversation histories, and deleting individual threads.
* **[ai.py](file:///app/routers/ai.py)**: Gateway endpoint that accepts chat requests, validates user permissions, and streams the AI prompt responses.

#### 📐 `app/schemas/` (Pydantic Models)
* **[auth.py](file:///app/schemas/auth.py)**: Input/Output schemas validating authentication actions (e.g. passwords, email structures).
* **[chat.py](file:///app/schemas/chat.py)**: Standardizes serialized outputs for conversations and message objects.
* **[ai.py](file:///app/schemas/ai.py)**: Validates incoming LLM prompts, chosen providers, model types, and response payload formatting.

#### 💼 `app/services/` (Core Business Logic)
* **[auth_service.py](file:///app/services/auth_service.py)**: Performs password hashing algorithms, formats JWT tokens, and manages database token creation and revocation.
* **[chat_service.py](file:///app/services/chat_service.py)**: Performs CRUD operations to fetch, rename, or purge conversations, and store chat message strings.
* **[ai_service.py](file:///app/services/ai_service.py)**: Resolves the active provider, counts tokens, formats conversational contexts, and initiates prompt streaming.
