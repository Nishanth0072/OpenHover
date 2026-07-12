# Open-Brain Backend — API Route Specifications

This document provides a comprehensive guide to all HTTP API endpoints exposed by the Open-Brain FastAPI server. 

All endpoints (except system health checks and basic auth endpoints) require bearer authentication via a JWT token.

---

## 🧭 Overview of Routers

The application groups endpoints by prefixes:
* **System**: Core health checking and server status.
* **Authentication (`/auth`)**: Handles account creation, sign-in, token expiration, rotation, and logout.
* **Users (`/users`)**: Access user profiles and subscriptions.
* **Chat History (`/chats`)**: Manage saved chats, load history, or delete threads.
* **AI Chat Gateway (`/ai`)**: Access text prompts, select LLM engines, and receive Server-Sent Event (SSE) responses.

---

## 🛠️ System Endpoints

### 1. `GET /health`
* **Summary:** Health Check
* **Authentication:** None
* **Description:** Verifies if the backend services (FastAPI, Redis, PostgreSQL) are operational.
* **Response (200 OK):**
  ```json
  {
    "status": "healthy",
    "service": "Open-Brain",
    "version": "1.0.0"
  }
  ```

---

## 🔐 Authentication Endpoints (`/auth`)

All requests in this router handle authentication credentials.

### 1. `POST /auth/register`
* **Summary:** User Registration
* **Authentication:** None
* **Description:** Registers a new user account. Passwords must be at least 8 characters long and contain at least one uppercase letter, one lowercase letter, and one digit.
* **Request Body:**
  ```json
  {
    "email": "user@example.com",
    "password": "SecurePassword123"
  }
  ```
* **Response (201 Created):**
  ```json
  {
    "access_token": "eyJhbGciOi...",
    "refresh_token": "eyJhbGciOi..."
  }
  ```
* **Errors:**
  * `409 Conflict`: Email already registered.
  * `422 Unprocessable Entity`: Password strength check failed.

### 2. `POST /auth/login`
* **Summary:** User Login
* **Authentication:** None
* **Description:** Verifies credentials and returns a new access/refresh token pair. Includes rate-limiting (maximum 5 failed attempts per 15 minutes).
* **Request Body:**
  ```json
  {
    "email": "user@example.com",
    "password": "SecurePassword123"
  }
  ```
* **Response (200 OK):**
  ```json
  {
    "access_token": "eyJhbGciOi...",
    "refresh_token": "eyJhbGciOi..."
  }
  ```
* **Errors:**
  * `401 Unauthorized`: Invalid email or password.
  * `429 Too Many Requests`: Login attempts exceeded rate limits.

### 3. `POST /auth/refresh`
* **Summary:** Refresh JWT Tokens
* **Authentication:** Bearer Token (Pass the **Refresh Token** in the `Authorization` header)
* **Description:** Exchanges an active refresh token for a brand new access and refresh token pair (token rotation). Once used, the old refresh token is revoked.
* **Headers:**
  * `Authorization: Bearer <refresh_token>`
* **Response (200 OK):**
  ```json
  {
    "access_token": "eyJhbGciOi...",
    "refresh_token": "eyJhbGciOi..."
  }
  ```
* **Errors:**
  * `401 Unauthorized`: Missing, expired, or revoked refresh token.

### 4. `POST /auth/logout`
* **Summary:** User Logout
* **Authentication:** Bearer Token (Pass the **Access Token** in the `Authorization` header)
* **Description:** Invalidates the current login session.
* **Headers:**
  * `Authorization: Bearer <access_token>`
* **Response (200 OK):**
  ```json
  {
    "message": "Successfully logged out."
  }
  ```

---

## 👤 User Profile Endpoints (`/users`)

### 1. `GET /users/me`
* **Summary:** Get user profile
* **Authentication:** Bearer Token (Pass the **Access Token** in the `Authorization` header)
* **Description:** Returns profile metadata of the currently logged-in user.
* **Headers:**
  * `Authorization: Bearer <access_token>`
* **Response (200 OK):**
  ```json
  {
    "id": "e4b6795e-14fa-4b68-80f0-8c29bf3e94be",
    "email": "user@example.com",
    "is_verified": false,
    "plan": "free",
    "created_at": "2026-07-04T12:00:00Z"
  }
  ```

---

## 🗄️ Chat History Endpoints (`/chats`)

Allows users to manage and browse archived conversations.

### 1. `GET /chats`
* **Summary:** List Conversations (Paginated)
* **Authentication:** Bearer Token (Pass the **Access Token** in the `Authorization` header)
* **Query Parameters:**
  * `page` (integer, default: `1`, minimum: `1`)
  * `page_size` (integer, default: `20`, range: `1-100`)
* **Headers:**
  * `Authorization: Bearer <access_token>`
* **Response (200 OK):**
  ```json
  {
    "conversations": [
      {
        "id": "4a613be3-0b19-48bb-bb85-dfa52f9547d2",
        "title": "Explain machine learning in one sentence...",
        "created_at": "2026-07-04T12:30:00Z",
        "updated_at": "2026-07-04T12:32:00Z"
      }
    ],
    "total": 1,
    "page": 1,
    "page_size": 20,
    "has_next": false
  }
  ```

### 2. `GET /chats/{chat_id}/history`
* **Summary:** Get Conversation History
* **Authentication:** Bearer Token (Pass the **Access Token** in the `Authorization` header)
* **Path Parameters:**
  * `chat_id` (string): UUID of the conversation.
* **Headers:**
  * `Authorization: Bearer <access_token>`
* **Response (200 OK):**
  ```json
  {
    "chat_id": "4a613be3-0b19-48bb-bb85-dfa52f9547d2",
    "title": "Explain machine learning in one sentence...",
    "messages": [
      {
        "id": "0dfbc460-70ff-4ea5-8025-055ea82db45a",
        "role": "user",
        "content": "Explain machine learning in one sentence.",
        "created_at": "2026-07-04T12:30:00Z"
      },
      {
        "id": "ef8a176e-56ee-4228-a3f2-178b1d283c79",
        "role": "assistant",
        "content": "Machine learning is a field of computer science that uses data to train algorithms to make predictions or decisions without being explicitly programmed.",
        "created_at": "2026-07-04T12:30:05Z"
      }
    ],
    "created_at": "2026-07-04T12:30:00Z",
    "updated_at": "2026-07-04T12:30:05Z"
  }
  ```
* **Errors:**
  * `404 Not Found`: Conversation does not exist or does not belong to the user.

### 3. `DELETE /chats/{chat_id}`
* **Summary:** Delete Conversation
* **Authentication:** Bearer Token (Pass the **Access Token** in the `Authorization` header)
* **Path Parameters:**
  * `chat_id` (string): UUID of the conversation to delete.
* **Headers:**
  * `Authorization: Bearer <access_token>`
* **Response (200 OK):**
  ```json
  {
    "message": "Conversation deleted successfully."
  }
  ```
* **Errors:**
  * `404 Not Found`: Conversation does not exist or does not belong to the user.

---

## 🤖 AI Gateway Endpoints (`/ai`)

Provides access to LLM prompt completions and customizable characters.

### 1. `POST /ai/chat`
* **Summary:** AI Chat (Server-Sent Events Streaming)
* **Authentication:** Bearer Token (Pass the **Access Token** in the `Authorization` header)
* **Description:** Sends a chat prompt to the selected provider (`openai`, `claude`, or `ollama`). Response is streamed live using Server-Sent Events (SSE). If `chat_id` is supplied, the prompt is appended to the existing thread. Otherwise, a new thread is created automatically.
* **Request Body:**
  ```json
  {
    "prompt": "Hello assistant, tell me a short joke.",
    "provider": "ollama",
    "chat_id": "4a613be3-0b19-48bb-bb85-dfa52f9547d2", 
    "model": "gemma3:4b"
  }
  ```
  *(Note: `chat_id` and `model` are optional).*
* **Stream Events (SSE):**
  1. **Event: `chat_start`** (Signals connection and returns conversation info):
     ```json
     data: {"chat_id": "4a613be3-0b19-48bb-bb85-dfa52f9547d2", "title": "Hello assistant..."}
     ```
  2. **Event: `chunk`** (Incremental tokens of assistant response):
     ```json
     data: {"text": "Why "}
     data: {"text": "don't "}
     data: {"text": "scientists "}
     ...
     ```
  3. **Event: `done`** (Terminates the stream):
     ```json
     data: {"status": "complete"}
     ```
* **Errors:**
  * `400 Bad Request`: Invalid provider selection.
  * `429 Too Many Requests`: Chat rate limit exceeded.

### 2. `GET /ai/characters`
* **Summary:** List AI Characters
* **Authentication:** Bearer Token (Pass the **Access Token** in the `Authorization` header)
* **Description:** Retrieves a list of predefined AI characters/agents (system personas, prompts, and avatar information).
* **Response (200 OK):**
  ```json
  [
    {
      "id": "code_buddy",
      "name": "Code Buddy",
      "system_prompt": "You are a professional software engineering assistant...",
      "description": "Expert in software engineering, debugging, and code reviews.",
      "avatar_url": "/avatars/code_buddy.png"
    }
  ]
  ```

---

## 📑 Built-in API Interactive Documentation

Once the server is running locally (e.g. at `http://localhost:8000`), you can view and test these endpoints interactively using your browser:
* **Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)
* **ReDoc:** [http://localhost:8000/redoc](http://localhost:8000/redoc)
* **JSON schema:** [http://localhost:8000/openapi.json](http://localhost:8000/openapi.json)
