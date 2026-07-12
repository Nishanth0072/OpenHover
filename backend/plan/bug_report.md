# Bug Report: Open-Brain Backend Service

This bug report highlights critical issues identified in the Open-Brain backend service codebase, specifically regarding authentication session management, AI provider adapter payloads, and character system prompt integration.

---

## 🐛 Summary of Identified Issues

| Severity | Issue Description | Component / File |
| :--- | :--- | :--- |
| **High** | [1. Session Invalidation Missing in `/auth/logout`](#1-session-invalidation-missing-in-authlogout) | `app/routers/auth.py` |
| **Medium** | [2. Missing Character Persona Integration in Chat Route](#2-missing-character-persona-integration-in-chat-route) | `app/routers/ai.py` |
| **Medium** | [3. Invalid System Message Format for Claude API](#3-invalid-system-message-format-for-claude-api) | `app/providers/claude.py` |
| **Low** | [4. Incorrect End-of-Stream `[DONE]` Check for Claude API](#4-incorrect-end-of-stream-done-check-for-claude-api) | `app/providers/claude.py` |
| **Low** | [5. Missing Explicit Database Commits in Auth Routes](#5-missing-explicit-database-commits-in-auth-routes) | `app/routers/auth.py` |

---

## 🔍 Detailed Descriptions & Remediation Plans

### 1. Session Invalidation Missing in `/auth/logout`
* **File:** [app/routers/auth.py](file:///c:/Users/mithun/backend%20openbrain/app/routers/auth.py#L237-L253)
* **Severity:** **High**
* **Description:** 
  The `/logout` endpoint is currently a stub that only logs a message and returns a success response. It does not perform any database or cache operations to invalidate active sessions or refresh tokens:
  ```python
  @router.post("/logout", response_model=MessageResponse, ...)
  async def logout(
      current_user: User = Depends(get_current_user),
      db: AsyncSession = Depends(get_db),
  ):
      """Log out the current user."""
      logger.info(f"User logged out: {current_user.email}")
      return MessageResponse(message="Successfully logged out.")
  ```
  Since the refresh tokens stored in the database remain valid, a logged-out client can still successfully call `/auth/refresh` and acquire a new access token, bypassing logout control.
* **Impact:** Users remain logged in on the backend even after calling logout, which is a major security flaw.
* **Remediation:**
  Modify `/auth/logout` to revoke the active session. If performing a global logout, bump the user's `token_version` in the database and cache the new version in Redis:
  ```python
  from app.services.auth_service import revoke_all_user_tokens
  
  # inside logout route
  await revoke_all_user_tokens(db, redis_client, current_user.id)
  ```
  *Note: This requires injecting the `redis_client` dependency in the `/logout` route.*

---

### 2. Missing Character Persona Integration in Chat Route
* **Files:** [app/routers/ai.py](file:///c:/Users/mithun/backend%20openbrain/app/routers/ai.py), [app/schemas/ai.py](file:///c:/Users/mithun/backend%20openbrain/app/schemas/ai.py)
* **Severity:** **Medium**
* **Description:** 
  The backend successfully loads AI character templates (e.g., Einstein, Code Wizard, Tutor) and exposes them through `GET /ai/characters`. However, the `ChatRequest` schema used by `POST /ai/chat` has no field to accept a `character_id` or `system_prompt` override. 
  Consequently, there is no mechanism to pass the character's system prompt to the AI provider, rendering the character selection feature non-functional in actual conversations.
* **Impact:** Users cannot use different character personas; all chats are conducted using the default model behavior.
* **Remediation:**
  1. Add an optional `character_id: Optional[str] = None` field to the `ChatRequest` schema.
  2. Look up the corresponding character system prompt inside `ai_chat` route.
  3. Prepend this system prompt to the message history payload sent to the AI providers.

---

### 3. Invalid System Message Format for Claude API
* **File:** [app/providers/claude.py](file:///c:/Users/mithun/backend%20openbrain/app/providers/claude.py#L32-L90)
* **Severity:** **Medium**
* **Description:** 
  The Claude adapter sends the message list as-is to the Anthropic Messages API. If character support is implemented and a system prompt is included in the `messages` array under the `system` role, it will fail:
  ```python
  payload = {
      "model": model,
      "max_tokens": 4096,
      "messages": messages, # Fails if 'system' role is inside this list
      "stream": True,
  }
  ```
  The Anthropic Messages API requires any system prompt to be passed as a top-level `"system"` parameter in the payload, rather than inside the `"messages"` list.
* **Impact:** Claude API calls will return a `400 Bad Request` if a system prompt is included in the messages list.
* **Remediation:**
  Modify `ClaudeProvider.stream_chat` to separate system messages from the messages history array and pass them via the top-level `system` key:
  ```python
  system_prompt = next((m["content"] for m in messages if m["role"] == "system"), None)
  filtered_messages = [m for m in messages if m["role"] != "system"]
  
  payload = {
      "model": model,
      "max_tokens": 4096,
      "messages": filtered_messages,
      "stream": True,
  }
  if system_prompt:
      payload["system"] = system_prompt
  ```

---

### 4. Incorrect End-of-Stream `[DONE]` Check for Claude API
* **File:** [app/providers/claude.py](file:///c:/Users/mithun/backend%20openbrain/app/providers/claude.py#L67-L72)
* **Severity:** **Low**
* **Description:** 
  The Claude provider attempts to detect the end of a stream by checking if the data chunk is `[DONE]`:
  ```python
  data_str = line[6:]  # Remove "data: " prefix
  if data_str == "[DONE]":
      break
  ```
  The Anthropic Claude API does not send a `[DONE]` string to close streams; that is an OpenAI protocol convention. Claude streams terminate naturally when the HTTP stream closes or when a `message_stop` event is yielded.
* **Impact:** Dead code that will never trigger, although the stream still terminates successfully when the underlying socket is closed.
* **Remediation:**
  Remove the `[DONE]` check or replace it with Anthropic-specific event tracking (e.g. breaking on `event_type == "message_stop"`).

---

### 5. Missing Explicit Database Commits in Auth Routes
* **File:** [app/routers/auth.py](file:///c:/Users/mithun/backend%20openbrain/app/routers/auth.py)
* **Severity:** **Low**
* **Description:** 
  Write operations in auth routes (e.g. `/register` creating a user, `/login` adding a refresh token, and `/refresh` rotating tokens) do not explicitly call `await db.commit()`. While the `get_db` dependency manager yields the session and calls `commit()` on completion of the request, implicit committing makes database interactions less transparent and harder to control, especially if an exception occurs during output serialization.
* **Impact:** Harder to manage transactional integrity and debug database session boundaries.
* **Remediation:**
  Add explicit `await db.commit()` calls at the end of successful write flows inside `register`, `login`, and `refresh_tokens` routers before returning payloads.
