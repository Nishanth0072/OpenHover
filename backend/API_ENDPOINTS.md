# 🧠 Open-Brain Backend — API Endpoints & Code Mapping

This document provides a comprehensive mapping of all HTTP API endpoints exposed by the Open-Brain FastAPI server to the exact files and code symbols implementing them.

---

## 🧭 Core Architectural Files

These files configure the core environment, database, caching, dependencies, and entrypoint of the backend application:

* **FastAPI Entrypoint**: [app/main.py](file:///c:/Users/mithun/backend%20openbrain/app/main.py) (Creates the app instance, configures CORS, and registers routers)
* **Configuration Manager**: [app/config.py](file:///c:/Users/mithun/backend%20openbrain/app/config.py) (Loads configuration using `pydantic_settings`)
* **Database Connection**: [app/database.py](file:///c:/Users/mithun/backend%20openbrain/app/database.py) (Sets up SQLAlchemy async engine and DB session factory)
* **Redis Manager**: [app/redis.py](file:///c:/Users/mithun/backend%20openbrain/app/redis.py) (Manages connections to Redis cache/store)
* **Auth Dependencies**: [app/dependencies.py](file:///c:/Users/mithun/backend%20openbrain/app/dependencies.py) (Implements `get_current_user` logic to validate JWTs)
* **Rate Limiter Middleware**: [app/middleware/rate_limiter.py](file:///c:/Users/mithun/backend%20openbrain/app/middleware/rate_limiter.py) (Enforces rate-limits on API requests)

---

## 🛠️ System Endpoints

### 1. `GET /health`
* **Summary:** Health Check
* **Authentication Required:** No
* **Description:** Verifies if the backend services are operational.
* **Implementing Files & Symbols:**
  * **Router File**: [app/main.py](file:///c:/Users/mithun/backend%20openbrain/app/main.py#L80-L92) -> `async def health_check()`
* **Example Response (200 OK):**
  ```json
  {
    "status": "healthy",
    "service": "Open-Brain",
    "version": "1.0.0"
  }
  ```

---

## 🔐 Authentication Endpoints (`/auth`)

### 1. `POST /auth/register/send-otp`
* **Summary:** Send Registration OTP (Step 1)
* **Authentication Required:** No
* **Description:** Validates password complexity, checks for duplicate email registration, generates a 6-digit OTP and a unique `registration_token` (UUIDv4), hashes the password and stores the session (email, password hash, OTP) grouped in Redis under `register:pending:{registration_token}`, and sends the OTP to the email.
* **Implementing Files & Symbols:**
  * **Router File**: [app/routers/auth.py](file:///c:/Users/mithun/backend%20openbrain/app/routers/auth.py#L65-L134) -> `async def send_registration_otp()`
  * **Request Payload Schema**: [RegisterInitiateRequest](file:///c:/Users/mithun/backend%20openbrain/app/schemas/auth.py#L5-L20) in `app/schemas/auth.py`
  * **Response Schema**: [RegisterInitiateResponse](file:///c:/Users/mithun/backend%20openbrain/app/schemas/auth.py#L21-L32) in `app/schemas/auth.py`
  * **User Model**: [User](file:///c:/Users/mithun/backend%20openbrain/app/models/user.py#L15) in `app/models/user.py`
  * **Services Called**:
    * `check_login_rate_limit` & `increment_login_attempts` in [app/services/auth_service.py](file:///c:/Users/mithun/backend%20openbrain/app/services/auth_service.py)
    * `hash_password`, `generate_otp` in [app/services/auth_service.py](file:///c:/Users/mithun/backend%20openbrain/app/services/auth_service.py)
    * `send_otp_email` in [app/services/email_service.py](file:///c:/Users/mithun/backend%20openbrain/app/services/email_service.py)
* **Example Request Payload:**
  ```json
  {
    "email": "user@example.com",
    "password": "SecurePassword123"
  }
  ```
* **Example Response (200 OK):**
  ```json
  {
    "registration_token": "550e8400-e29b-41d4-a716-446655440000",
    "message": "OTP sent to your email address."
  }
  ```

---

### 2. `POST /auth/register`
* **Summary:** Register a New User (Step 2)
* **Authentication Required:** No
* **Description:** Retrieves the pending registration session from Redis using the provided `registration_token`, verifies that the email and OTP match the session, creates the User record in PostgreSQL, and generates access and refresh tokens.
* **Implementing Files & Symbols:**
  * **Router File**: [app/routers/auth.py](file:///c:/Users/mithun/backend%20openbrain/app/routers/auth.py#L141-L224) -> `async def register()`
  * **Request Payload Schema**: [RegisterVerifyRequest](file:///c:/Users/mithun/backend%20openbrain/app/schemas/auth.py#L47-L62) in `app/schemas/auth.py`
  * **Response Schema**: [TokenResponse](file:///c:/Users/mithun/backend%20openbrain/app/schemas/auth.py#L99-L114) in `app/schemas/auth.py`
  * **User Model**: [User](file:///c:/Users/mithun/backend%20openbrain/app/models/user.py#L15) in `app/models/user.py`
  * **Services Called**:
    * `create_access_token`, `create_refresh_token`, `store_refresh_token` in [app/services/auth_service.py](file:///c:/Users/mithun/backend%20openbrain/app/services/auth_service.py)
* **Example Request Payload:**
  ```json
  {
    "registration_token": "550e8400-e29b-41d4-a716-446655440000",
    "email": "user@example.com",
    "otp": "482915"
  }
  ```
* **Example Response (201 Created):**
  ```json
  {
    "access_token": "eyJhbGciOi...",
    "refresh_token": "eyJhbGciOi...",
    "token_type": "bearer"
  }
  ```

---

### 3. `POST /auth/login`
* **Summary:** User Login (MFA Step 1)
* **Authentication Required:** No
* **Description:** Validates credentials. If correct, generates a short-lived `mfa_token` (JWT challenge) and sends a login OTP to the user's email.
* **Implementing Files & Symbols:**
  * **Router File**: [app/routers/auth.py](file:///c:/Users/mithun/backend%20openbrain/app/routers/auth.py#L230-L294) -> `async def login()`
  * **Request Payload Schema**: [LoginRequest](file:///c:/Users/mithun/backend%20openbrain/app/schemas/auth.py#L65-L80) in `app/schemas/auth.py`
  * **Response Schema**: [LoginMFAChallengeResponse](file:///c:/Users/mithun/backend%20openbrain/app/schemas/auth.py#L116-L131) in `app/schemas/auth.py`
  * **User Model**: [User](file:///c:/Users/mithun/backend%20openbrain/app/models/user.py#L15) in `app/models/user.py`
  * **Services Called**:
    * `verify_password`, `generate_otp`, `store_otp`, `create_mfa_token` in [app/services/auth_service.py](file:///c:/Users/mithun/backend%20openbrain/app/services/auth_service.py)
    * `send_otp_email` in [app/services/email_service.py](file:///c:/Users/mithun/backend%20openbrain/app/services/email_service.py)
* **Example Request Payload:**
  ```json
  {
    "email": "user@example.com",
    "password": "SecurePassword123"
  }
  ```
* **Example Response (200 OK):**
  ```json
  {
    "otp_required": true,
    "mfa_token": "eyJhbGciOi...",
    "email": "user@example.com"
  }
  ```

---

### 4. `POST /auth/login/verify`
* **Summary:** Verify Login OTP (MFA Step 2)
* **Authentication Required:** No
* **Description:** Validates the login OTP and MFA challenge token. Returns final JWT access and refresh tokens.
* **Implementing Files & Symbols:**
  * **Router File**: [app/routers/auth.py](file:///c:/Users/mithun/backend%20openbrain/app/routers/auth.py#L301-L376) -> `async def verify_login_otp()`
  * **Request Payload Schema**: [VerifyLoginOTPRequest](file:///c:/Users/mithun/backend%20openbrain/app/schemas/auth.py#L82-L97) in `app/schemas/auth.py`
  * **Response Schema**: [TokenResponse](file:///c:/Users/mithun/backend%20openbrain/app/schemas/auth.py#L99-L114) in `app/schemas/auth.py`
  * **User Model**: [User](file:///c:/Users/mithun/backend%20openbrain/app/models/user.py#L15) in `app/models/user.py`
  * **Services Called**:
    * `decode_token`, `verify_otp`, `reset_login_attempts`, `create_access_token`, `create_refresh_token`, `store_refresh_token` in [app/services/auth_service.py](file:///c:/Users/mithun/backend%20openbrain/app/services/auth_service.py)
* **Example Request Payload:**
  ```json
  {
    "mfa_token": "eyJhbGciOi...",
    "otp": "482915"
  }
  ```
* **Example Response (200 OK):**
  ```json
  {
    "access_token": "eyJhbGciOi...",
    "refresh_token": "eyJhbGciOi...",
    "token_type": "bearer"
  }
  ```

---

### 5. `POST /auth/refresh`
* **Summary:** Refresh JWT Tokens
* **Authentication Required:** Bearer Token (Pass **Refresh Token** in the `Authorization` header)
* **Description:** Exchange an active refresh token for a new access/refresh token pair. The old refresh token is revoked.
* **Implementing Files & Symbols:**
  * **Router File**: [app/routers/auth.py](file:///c:/Users/mithun/backend%20openbrain/app/routers/auth.py#L382-L465) -> `async def refresh_tokens()`
  * **Response Schema**: [TokenResponse](file:///c:/Users/mithun/backend%20openbrain/app/schemas/auth.py#L99-L114) in `app/schemas/auth.py`
  * **User Model**: [User](file:///c:/Users/mithun/backend%20openbrain/app/models/user.py#L15) in `app/models/user.py`
  * **Services Called**:
    * `decode_token`, `validate_token_version`, `is_refresh_token_valid`, `revoke_refresh_token`, `create_access_token`, `create_refresh_token`, `store_refresh_token` in [app/services/auth_service.py](file:///c:/Users/mithun/backend%20openbrain/app/services/auth_service.py)
* **Example Response (200 OK):**
  ```json
  {
    "access_token": "eyJhbGciOi...",
    "refresh_token": "eyJhbGciOi...",
    "token_type": "bearer"
  }
  ```

---

### 6. `POST /auth/logout`
* **Summary:** Logout Current Session
* **Authentication Required:** Bearer Token (Pass **Access Token** in the `Authorization` header)
* **Description:** Logs out the current session, blacklists the access token, and optionally revokes the refresh token.
* **Implementing Files & Symbols:**
  * **Router File**: [app/routers/auth.py](file:///c:/Users/mithun/backend%20openbrain/app/routers/auth.py#L472-L506) -> `async def logout()`
  * **Request Payload Schema**: [LogoutRequest](file:///c:/Users/mithun/backend%20openbrain/app/schemas/auth.py#L157-L165) in `app/schemas/auth.py`
  * **Response Schema**: [MessageResponse](file:///c:/Users/mithun/backend%20openbrain/app/schemas/auth.py#L145-L149) in `app/schemas/auth.py`
  * **Services Called**:
    * `revoke_current_session` in [app/services/auth_service.py](file:///c:/Users/mithun/backend%20openbrain/app/services/auth_service.py)
* **Example Response (200 OK):**
  ```json
  {
    "message": "Successfully logged out."
  }
  ```

---

### 7. `POST /auth/logout-all`
* **Summary:** Logout All Devices
* **Authentication Required:** Bearer Token (Pass **Access Token** in the `Authorization` header)
* **Description:** Invalidates all sessions/tokens for the user by incrementing the database `token_version`.
* **Implementing Files & Symbols:**
  * **Router File**: [app/routers/auth.py](file:///c:/Users/mithun/backend%20openbrain/app/routers/auth.py#L512-L533) -> `async def logout_all()`
  * **Response Schema**: [MessageResponse](file:///c:/Users/mithun/backend%20openbrain/app/schemas/auth.py#L145-L149) in `app/schemas/auth.py`
  * **Services Called**:
    * `revoke_all_user_tokens` in [app/services/auth_service.py](file:///c:/Users/mithun/backend%20openbrain/app/services/auth_service.py)
* **Example Response (200 OK):**
  ```json
  {
    "message": "Successfully logged out from all devices."
  }
  ```

---

## 👤 User Profile Endpoints (`/users`)

### 1. `GET /users/me`
* **Summary:** Get Current User Profile
* **Authentication Required:** Bearer Token (Pass **Access Token** in the `Authorization` header)
* **Description:** Retrieves profile metadata for the currently authenticated user.
* **Implementing Files & Symbols:**
  * **Router File**: [app/routers/users.py](file:///c:/Users/mithun/backend%20openbrain/app/routers/users.py#L19-L36) -> `async def get_me()`
  * **Response Schema**: [UserProfileResponse](file:///c:/Users/mithun/backend%20openbrain/app/schemas/auth.py#L133-L143) in `app/schemas/auth.py`
  * **User Model**: [User](file:///c:/Users/mithun/backend%20openbrain/app/models/user.py#L15) in `app/models/user.py`
  * **Rate Limiter**: Uses `check_rate_limit` from [app/middleware/rate_limiter.py](file:///c:/Users/mithun/backend%20openbrain/app/middleware/rate_limiter.py)
* **Example Response (200 OK):**
  ```json
  {
    "id": "e4b6795e-14fa-4b68-80f0-8c29bf3e94be",
    "email": "user@example.com",
    "is_verified": true,
    "plan": "free",
    "created_at": "2026-07-04T12:00:00Z"
  }
  ```

---

## 🗄️ Chat History Endpoints (`/chats`)

### 1. `GET /chats`
* **Summary:** List Conversations (Paginated)
* **Authentication Required:** Bearer Token (Pass **Access Token** in the `Authorization` header)
* **Description:** Returns a paginated list of chat threads created by the user.
* **Implementing Files & Symbols:**
  * **Router File**: [app/routers/chats.py](file:///c:/Users/mithun/backend%20openbrain/app/routers/chats.py#L32-L62) -> `async def get_chats()`
  * **Response Schema**: [PaginatedConversationsResponse](file:///c:/Users/mithun/backend%20openbrain/app/schemas/chat.py#L46-L53) (wrapping [ConversationListItem](file:///c:/Users/mithun/backend%20openbrain/app/schemas/chat.py#L12-L19)) in `app/schemas/chat.py`
  * **Database Model**: [Conversation](file:///c:/Users/mithun/backend%20openbrain/app/models/conversation.py#L15) in `app/models/conversation.py`
  * **Services Called**:
    * `list_conversations` in [app/services/chat_service.py](file:///c:/Users/mithun/backend%20openbrain/app/services/chat_service.py)
* **Example Response (200 OK):**
  ```json
  {
    "conversations": [
      {
        "chat_id": "4a613be3-0b19-48bb-bb85-dfa52f9547d2",
        "title": "Explain machine learning in one sentence...",
        "updated_at": "2026-07-04T12:32:00Z"
      }
    ],
    "total": 1,
    "page": 1,
    "page_size": 20,
    "has_next": false
  }
  ```

---

### 2. `GET /chats/{chat_id}/history`
* **Summary:** Get Conversation History
* **Authentication Required:** Bearer Token (Pass **Access Token** in the `Authorization` header)
* **Description:** Fetches all user/assistant message turns inside a specific chat thread.
* **Implementing Files & Symbols:**
  * **Router File**: [app/routers/chats.py](file:///c:/Users/mithun/backend%20openbrain/app/routers/chats.py#L65-L103) -> `async def get_chat_history()`
  * **Response Schema**: [ConversationHistoryResponse](file:///c:/Users/mithun/backend%20openbrain/app/schemas/chat.py#L36-L44) (wrapping list of [MessageSchema](file:///c:/Users/mithun/backend%20openbrain/app/schemas/chat.py#L22-L34)) in `app/schemas/chat.py`
  * **Database Models**: [Conversation](file:///c:/Users/mithun/backend%20openbrain/app/models/conversation.py#L15) & [Message](file:///c:/Users/mithun/backend%20openbrain/app/models/message.py#L15)
  * **Services Called**:
    * `get_conversation_history` in [app/services/chat_service.py](file:///c:/Users/mithun/backend%20openbrain/app/services/chat_service.py)
* **Example Response (200 OK):**
  ```json
  {
    "chat_id": "4a613be3-0b19-48bb-bb85-dfa52f9547d2",
    "title": "Explain machine learning...",
    "messages": [
      {
        "id": "0dfbc460-70ff-4ea5-8025-055ea82db45a",
        "role": "user",
        "content": "Explain machine learning.",
        "provider_used": null,
        "token_count": null,
        "is_partial": false,
        "created_at": "2026-07-04T12:30:00Z"
      },
      {
        "id": "ef8a176e-56ee-4228-a3f2-178b1d283c79",
        "role": "assistant",
        "content": "Machine learning uses data to train models...",
        "provider_used": "claude",
        "token_count": 12,
        "is_partial": false,
        "created_at": "2026-07-04T12:30:05Z"
      }
    ],
    "created_at": "2026-07-04T12:30:00Z",
    "updated_at": "2026-07-04T12:30:05Z"
  }
  ```

---

### 3. `DELETE /chats/{chat_id}`
* **Summary:** Delete Conversation
* **Authentication Required:** Bearer Token (Pass **Access Token** in the `Authorization` header)
* **Description:** Deletes a conversation thread and all its messages.
* **Implementing Files & Symbols:**
  * **Router File**: [app/routers/chats.py](file:///c:/Users/mithun/backend%20openbrain/app/routers/chats.py#L106-L137) -> `async def delete_chat()`
  * **Response Schema**: [MessageResponse](file:///c:/Users/mithun/backend%20openbrain/app/schemas/auth.py#L145-L149) in `app/schemas/auth.py`
  * **Database Model**: [Conversation](file:///c:/Users/mithun/backend%20openbrain/app/models/conversation.py#L15) in `app/models/conversation.py`
  * **Services Called**:
    * `delete_conversation` in [app/services/chat_service.py](file:///c:/Users/mithun/backend%20openbrain/app/services/chat_service.py)
* **Example Response (200 OK):**
  ```json
  {
    "message": "Conversation deleted successfully."
  }
  ```

---

## 🤖 AI Gateway Endpoints (`/ai`)

### 1. `POST /ai/chat`
* **Summary:** AI Chat (Streaming response)
* **Authentication Required:** Bearer Token (Pass **Access Token** in the `Authorization` header)
* **Description:** Sends a chat prompt to Claude, OpenAI, or Ollama. Returns a live stream using Server-Sent Events (SSE).
* **Implementing Files & Symbols:**
  * **Router File**: [app/routers/ai.py](file:///c:/Users/mithun/backend%20openbrain/app/routers/ai.py#L28-L176) -> `async def ai_chat()`
  * **Request Payload Schema**: [ChatRequest](file:///c:/Users/mithun/backend%20openbrain/app/schemas/ai.py#L11-L40) in `app/schemas/ai.py`
  * **Database Models**: [Conversation](file:///c:/Users/mithun/backend%20openbrain/app/models/conversation.py#L15) & [Message](file:///c:/Users/mithun/backend%20openbrain/app/models/message.py#L15)
  * **Services & Providers Called**:
    * `get_or_create_conversation`, `add_message`, `get_conversation_history` in [app/services/chat_service.py](file:///c:/Users/mithun/backend%20openbrain/app/services/chat_service.py)
    * `stream_ai_response`, `load_characters` in [app/services/ai_service.py](file:///c:/Users/mithun/backend%20openbrain/app/services/ai_service.py)
    * Concrete LLM Engines:
      * [app/providers/claude.py](file:///c:/Users/mithun/backend%20openbrain/app/providers/claude.py)
      * [app/providers/openai_provider.py](file:///c:/Users/mithun/backend%20openbrain/app/providers/openai_provider.py)
      * [app/providers/ollama.py](file:///c:/Users/mithun/backend%20openbrain/app/providers/ollama.py)
* **Example Request Payload:**
  ```json
  {
    "prompt": "Explain Quantum computing briefly.",
    "provider": "claude",
    "model": "claude-3-5-sonnet-20241022",
    "character_id": "code_buddy"
  }
  ```
* **Example Stream Events (SSE format):**
  ```text
  event: chat_start
  data: {"chat_id": "4a613be3-0b19-48bb-bb85-dfa52f9547d2", "title": "Explain Quantum..."}

  event: chunk
  data: {"text": "Quantum "}

  event: chunk
  data: {"text": "computing "}

  event: chunk
  data: {"text": "uses..."}

  event: done
  data: {"status": "complete"}
  ```

---

### 2. `GET /ai/characters`
* **Summary:** List AI Characters
* **Authentication Required:** Bearer Token (Pass **Access Token** in the `Authorization` header)
* **Description:** Retrieves the list of predefined AI personas (system prompt, descriptions, etc.) loaded from local resources.
* **Implementing Files & Symbols:**
  * **Router File**: [app/routers/ai.py](file:///c:/Users/mithun/backend%20openbrain/app/routers/ai.py#L178-L189) -> `async def get_characters()`
  * **Response Schema**: List of [CharacterSchema](file:///c:/Users/mithun/backend%20openbrain/app/schemas/ai.py#L42-L50) in `app/schemas/ai.py`
  * **Services Called**:
    * `load_characters` in [app/services/ai_service.py](file:///c:/Users/mithun/backend%20openbrain/app/services/ai_service.py)
* **Example Response (200 OK):**
  ```json
  [
    {
      "id": "code_buddy",
      "name": "Code Buddy",
      "description": "Expert in software engineering, debugging, and code reviews.",
      "system_prompt": "You are a professional software engineering assistant...",
      "avatar": "/avatars/code_buddy.png"
    }
  ]
  ```
