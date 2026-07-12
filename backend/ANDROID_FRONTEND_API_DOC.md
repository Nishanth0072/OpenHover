# 📱 Open-Brain Android Frontend Integration & API Documentation

This document serves as the official API integration guide and specifications for Android developers building the Open-Brain mobile application. It covers network configurations, clean architecture setups, JWT/MFA authentication flows, paginated chat histories, and Server-Sent Event (SSE) AI streaming in Kotlin.

---

## 🗺️ 1. Networking & Local Development Setup

When developing the Android frontend against a locally running backend, you must configure network addresses and security settings correctly.

### A. Emulators vs. Physical Devices
* **Android Emulator:** Accesses the host's `localhost` via the special IP address `10.0.2.2`.
  * **Base URL:** `http://10.0.2.2:8000`
* **Physical Device:** Must connect via a shared Wi-Fi network using the host's local IP (e.g., `192.168.x.x`), or connect to the public HTTPS URL exposed by the **Cloudflare Tunnel**.
  * **Base URL:** `https://your-cloudflare-subdomain.trycloudflare.com`

### B. Network Security Configuration (Cleartext HTTP)
Android blocks cleartext HTTP traffic by default. If testing locally over `http://10.0.2.2:8000` without TLS, you must configure a network security exception.

1. Create a file at `app/src/main/res/xml/network_security_config.xml`:
   ```xml
   <?xml version="1.0" encoding="utf-8"?>
   <network-security-config>
       <domain-config cleartextTrafficPermitted="true">
           <!-- Allow cleartext traffic for local emulator development -->
           <domain includeSubdomains="true">10.0.2.2</domain>
           <domain includeSubdomains="true">localhost</domain>
       </domain-config>
   </network-security-config>
   ```

2. Reference this configuration in your `app/src/main/AndroidManifest.xml`:
   ```xml
   <application
       android:name=".OpenBrainApplication"
       android:networkSecurityConfig="@xml/network_security_config"
       android:usesCleartextTraffic="true"
       ... >
   </application>
   ```

---

## 🏗️ 2. Architectural Design & Gradle Dependencies

We recommend using **Clean Architecture** combined with **MVVM/MVI** for the presentation layer, relying on **Jetpack Compose** for a modern, reactive UI.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           PRESENTATION LAYER                            │
│           Jetpack Compose UI (Screens, Composables, Themes)             │
│                                   ▲                                     │
│                                   │ (Exposes UI State as StateFlow)     │
│             ViewModels (Manages state & handles user events)            │
└───────────────────────────────────┬─────────────────────────────────────┘
                                    │
                                    ▼ (Calls Use Cases / Repositories)
┌─────────────────────────────────────────────────────────────────────────┐
│                               DATA LAYER                                │
│       Repositories (Single source of truth, handles caching/network)    │
│           ┌───────────────────────┴───────────────────────┐             │
│           ▼ (REST API calls)                              ▼ (Local Cache)│
│     Retrofit Service                              Room Database /       │
│     & OkHttp Client                               EncryptedPrefs        │
└─────────────────────────────────────────────────────────────────────────┘
```

### Required Gradle Dependencies (`build.gradle.kts`)
Ensure the following libraries are added to your project:

```kotlin
dependencies {
    // Retrofit & OkHttp
    implementation("com.squareup.retrofit2:retrofit:2.9.0")
    implementation("com.squareup.retrofit2:converter-gson:2.9.0")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation("com.squareup.okhttp3:logging-interceptor:4.12.0")
    
    // OkHttp Server-Sent Events (SSE) Extension
    implementation("com.squareup.okhttp3:okhttp-sse:4.12.0")

    // Dagger Hilt (Dependency Injection)
    implementation("com.google.dagger:hilt-android:2.50")
    kapt("com.google.dagger:hilt-compiler:2.50")

    // Coroutines & Lifecycle Lifecycle Extensions
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.7.3")
    implementation("androidx.lifecycle:lifecycle-viewmodel-ktx:2.7.0")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.7.0")
    
    // Security (Encrypted SharedPreferences)
    implementation("androidx.security:security-crypto:1.1.0-alpha06")
}
```

---

## 🔐 3. Authentication & Session Management

The Open-Brain backend implements two-step verification for registration/login and JWT access token rotation.

```
                  ┌────────────────────────────────────────┐
                  │           Auth Token Storage           │
                  │   EncryptedSharedPreferences (AES)     │
                  └───────────────────┬────────────────────┘
                                      │
                                      ▼ (Provide tokens / Check expiry)
                     ┌──────────────────────────────────┐
                     │   OkHttp Interceptor/Auth Chain  │
                     └────────────────┬─────────────────┘
                                      │
           ┌──────────────────────────┴──────────────────────────┐
           ▼                                                     ▼
┌───────────────────────┐                               ┌───────────────────────┐
│ AuthInterceptor       │                               │ TokenAuthenticator    │
│ Adds "Authorization:  │                               │ Intercepts 401s,      │
│ Bearer <access_token>"│                               │ requests /auth/refresh│
│ to outbound requests. │                               │ & retries transparently│
└───────────────────────┘                               └───────────────────────┘
```

### A. Token Storage Implementation
Store tokens securely using `EncryptedSharedPreferences` to prevent root-access extraction.

```kotlin
package com.openbrain.data.local

import android.content.Context
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKeys
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class TokenStorage @Inject constructor(context: Context) {
    private val masterKeyAlias = MasterKeys.getOrCreate(MasterKeys.AES256_GCM_SPEC)
    
    private val prefs = EncryptedSharedPreferences.create(
        "open_brain_secure_prefs",
        masterKeyAlias,
        context,
        EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
        EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
    )

    fun saveTokens(accessToken: String, refreshToken: String) {
        prefs.edit()
            .putString("access_token", accessToken)
            .putString("refresh_token", refreshToken)
            .apply()
    }

    fun getAccessToken(): String? = prefs.getString("access_token", null)
    
    fun getRefreshToken(): String? = prefs.getString("refresh_token", null)

    fun clearTokens() {
        prefs.edit().remove("access_token").remove("refresh_token").apply()
    }
}
```

### B. OkHttp Token Interceptor & Authenticator
This handles adding access tokens automatically to all authenticated requests and silently rotating expired access tokens behind the scenes.

```kotlin
package com.openbrain.data.remote

import com.openbrain.data.local.TokenStorage
import okhttp3.*
import okhttp3.Authenticator
import java.io.IOException
import javax.inject.Inject
import javax.inject.Provider

/**
 * Adds the Access Token header to all outgoing requests.
 */
class AuthInterceptor @Inject constructor(
    private val tokenStorage: TokenStorage
) : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val requestBuilder = chain.request().newBuilder()
        tokenStorage.getAccessToken()?.let { token ->
            requestBuilder.header("Authorization", "Bearer $token")
        }
        return chain.proceed(requestBuilder.build())
    }
}

/**
 * Automatically catches 401 Unauthorized responses, runs a token refresh request,
 * saves the new credentials, and retries the original request.
 */
class TokenAuthenticator @Inject constructor(
    private val tokenStorage: TokenStorage,
    private val apiServiceProvider: Provider<OpenBrainApiService> // Use Provider to prevent circular dependency in Hilt
) : Authenticator {

    override fun authenticate(route: Route?, response: Response): Request? {
        val refreshToken = tokenStorage.getRefreshToken() ?: return null

        synchronized(this) {
            val currentAccess = tokenStorage.getAccessToken()
            val requestAccess = response.request.header("Authorization")?.replace("Bearer ", "")

            // If access token changed, another thread already refreshed it; retry original request immediately
            if (currentAccess != requestAccess) {
                return response.request.newBuilder()
                    .header("Authorization", "Bearer $currentAccess")
                    .build()
            }

            // Sync API call to refresh tokens
            val apiService = apiServiceProvider.get()
            val refreshCall = apiService.refreshTokensSync("Bearer $refreshToken")
            val refreshResponse = refreshCall.execute()

            if (refreshResponse.isSuccessful && refreshResponse.body() != null) {
                val newTokens = refreshResponse.body()!!
                tokenStorage.saveTokens(newTokens.access_token, newTokens.refresh_token)
                
                return response.request.newBuilder()
                    .header("Authorization", "Bearer ${newTokens.access_token}")
                    .build()
            } else {
                // Refresh failed: logout user, wipe tokens, and redirect to Auth Screen
                tokenStorage.clearTokens()
                triggerGlobalLogout()
                return null
            }
        }
    }

    private fun triggerGlobalLogout() {
        // Broadcaster, EventBus, or Navigation action to force user logout
    }
}
```

---

## 📦 4. Data Transfer Objects (DTOs) & Retrofit Interface

### A. Kotlin Data Transfer Objects
Map these directly to the FastAPI Pydantic requests/responses.

```kotlin
package com.openbrain.data.remote

import com.google.gson.annotations.SerializedName

// --- Authentication Flows ---
data class RegisterInitiateRequest(
    val email: String,
    val password: String
)

data class RegisterInitiateResponse(
    @SerializedName("registration_token") val registrationToken: String,
    val message: String
)

data class RegisterVerifyRequest(
    @SerializedName("registration_token") val registrationToken: String,
    val email: String,
    val otp: String
)

data class LoginRequest(
    val email: String,
    val password: String
)

data class LoginMFAChallengeResponse(
    @SerializedName("otp_required") val otpRequired: Boolean,
    @SerializedName("mfa_token") val mfaToken: String,
    val email: String
)

data class VerifyLoginOTPRequest(
    @SerializedName("mfa_token") val mfaToken: String,
    val otp: String
)

data class TokenResponse(
    @SerializedName("access_token") val access_token: String,
    @SerializedName("refresh_token") val refresh_token: String,
    @SerializedName("token_type") val tokenType: String
)

// --- Folder DTOs ---
data class FolderDto(
    val id: String,
    val name: String,
    @SerializedName("created_at") val createdAt: String
)

data class CreateFolderRequest(
    val name: String
)

// --- Attachments ---
data class AttachmentDto(
    val id: String,
    val filename: String,
    @SerializedName("content_type") val contentType: String,
    @SerializedName("size_bytes") val sizeBytes: Long,
    val url: String
)

// --- Billing ---
data class BillingPlanDto(
    val id: String,
    val name: String,
    val price: Int,
    val currency: String
)

data class SubscribeRequest(
    @SerializedName("plan_id") val planId: String
)

data class CheckoutResponse(
    @SerializedName("checkout_url") val checkoutUrl: String
)

data class InvoiceDto(
    val id: String,
    val amount: Int,
    val date: String,
    @SerializedName("pdf_url") val pdfUrl: String
)

// --- Notifications & Support ---
data class NotificationDto(
    val id: String,
    val title: String,
    val message: String,
    val read: Boolean
)

data class SupportRequestDto(
    val name: String,
    val email: String,
    val message: String
)

// --- Admin ---
data class AdminStatsDto(
    @SerializedName("total_users") val totalUsers: Int,
    @SerializedName("premium_users") val premiumUsers: Int,
    @SerializedName("total_messages") val totalMessages: Int,
    @SerializedName("total_revenue") val totalRevenue: Int
)

// --- User Profile ---
data class UserProfileResponse(
    val id: String,
    val email: String,
    @SerializedName("is_verified") val isVerified: Boolean,
    val plan: String,
    @SerializedName("created_at") val createdAt: String
)

// --- Chat History ---
data class ConversationListItem(
    @SerializedName("chat_id") val chatId: String,
    val title: String,
    @SerializedName("updated_at") val updatedAt: String
)

data class PaginatedConversationsResponse(
    val conversations: List<ConversationListItem>,
    val total: Int,
    val page: Int,
    @SerializedName("page_size") val pageSize: Int,
    @SerializedName("has_next") val hasNext: Boolean
)

data class MessageSchema(
    val id: String,
    val role: String, // "user" or "assistant"
    val content: String,
    @SerializedName("provider_used") val providerUsed: String?,
    @SerializedName("token_count") val tokenCount: Int?,
    @SerializedName("is_partial") val isPartial: Boolean,
    @SerializedName("created_at") val createdAt: String
)

data class ConversationHistoryResponse(
    @SerializedName("chat_id") val chatId: String,
    val title: String,
    val messages: List<MessageSchema>,
    @SerializedName("created_at") val createdAt: String,
    @SerializedName("updated_at") val updatedAt: String
)

// --- AI Personas ---
data class CharacterSchema(
    val id: String,
    val name: String,
    val description: String,
    @SerializedName("system_prompt") val systemPrompt: String,
    val avatar: String?
)

// --- Generic Responses ---
data class MessageResponse(
    val message: String
)

data class ErrorResponse(
    val detail: String
)
```

### B. Retrofit API Service Definition
Standard HTTP API paths for OAuth2, Profile, Chats, and Character definitions.

```kotlin
package com.openbrain.data.remote

import retrofit2.Call
import retrofit2.Response
import retrofit2.http.*

interface OpenBrainApiService {

    // --- Authentication ---

    @POST("/auth/register/send-otp")
    suspend fun registerInitiate(
        @Body request: RegisterInitiateRequest
    ): Response<RegisterInitiateResponse>

    @POST("/auth/register")
    suspend fun registerVerify(
        @Body request: RegisterVerifyRequest
    ): Response<TokenResponse>

    @POST("/auth/login")
    suspend fun loginInitiate(
        @Body request: LoginRequest
    ): Response<LoginMFAChallengeResponse>

    @POST("/auth/login/verify")
    suspend fun loginVerify(
        @Body request: VerifyLoginOTPRequest
    ): Response<TokenResponse>

    @POST("/auth/logout")
    suspend fun logout(): Response<MessageResponse>

    // Note: Executed synchronously inside TokenAuthenticator.
    // Auth header holds the Refresh Token instead of Access Token here.
    @POST("/auth/refresh")
    fun refreshTokensSync(
        @Header("Authorization") bearerRefreshToken: String
    ): Call<TokenResponse>

    // --- Folders ---
    @GET("/folders")
    suspend fun getFolders(): Response<List<FolderDto>>

    @POST("/folders")
    suspend fun createFolder(
        @Body request: CreateFolderRequest
    ): Response<FolderDto>

    @PATCH("/folders/{folder_id}")
    suspend fun renameFolder(
        @Path("folder_id") folderId: String,
        @Body request: CreateFolderRequest
    ): Response<FolderDto>

    @DELETE("/folders/{folder_id}")
    suspend fun deleteFolder(
        @Path("folder_id") folderId: String
    ): Response<MessageResponse>

    // --- Attachments ---
    @Multipart
    @POST("/chats/{chat_id}/attachments")
    suspend fun uploadAttachment(
        @Path("chat_id") chatId: String,
        @Part file: okhttp3.MultipartBody.Part
    ): Response<AttachmentDto>

    @Streaming
    @GET("/attachments/{attachment_id}")
    suspend fun downloadAttachment(
        @Path("attachment_id") attachmentId: String
    ): Response<okhttp3.ResponseBody>

    @DELETE("/attachments/{attachment_id}")
    suspend fun deleteAttachment(
        @Path("attachment_id") attachmentId: String
    ): Response<MessageResponse>

    // --- Billing ---
    @GET("/billing/plans")
    suspend fun getBillingPlans(): Response<List<BillingPlanDto>>

    @POST("/billing/subscribe")
    suspend fun subscribe(
        @Body request: SubscribeRequest
    ): Response<CheckoutResponse>

    @POST("/billing/cancel")
    suspend fun cancelSubscription(): Response<MessageResponse>

    @GET("/billing/invoices")
    suspend fun getInvoices(): Response<List<InvoiceDto>>

    // --- Notifications ---
    @GET("/notifications")
    suspend fun getNotifications(): Response<List<NotificationDto>>

    @PATCH("/notifications/{id}/read")
    suspend fun markNotificationRead(
        @Path("id") id: String
    ): Response<NotificationDto>

    // --- Support ---
    @POST("/support/contact")
    suspend fun submitSupportRequest(
        @Body request: SupportRequestDto
    ): Response<MessageResponse>

    // --- Admin ---
    @GET("/admin/stats")
    suspend fun getAdminStats(): Response<AdminStatsDto>

    // --- User Profiles ---

    @GET("/users/me")
    suspend fun getUserProfile(): Response<UserProfileResponse>

    // --- Conversations/History ---

    @GET("/chats")
    suspend fun getChats(
        @Query("page") page: Int,
        @Query("page_size") pageSize: Int
    ): Response<PaginatedConversationsResponse>

    @GET("/chats/{chat_id}/history")
    suspend fun getChatHistory(
        @Path("chat_id") chatId: String
    ): Response<ConversationHistoryResponse>

    @DELETE("/chats/{chat_id}")
    suspend fun deleteChat(
        @Path("chat_id") chatId: String
    ): Response<MessageResponse>

    // --- AI Characters ---

    @GET("/ai/characters")
    suspend fun getCharacters(): Response<List<CharacterSchema>>
}
```

---

## 🤖 5. Consuming Server-Sent Events (SSE) AI Streams

The AI Gateway endpoint `/ai/chat` uses POST-based Server-Sent Events (SSE) to stream completion tokens. Because standard `EventSource` clients do not support headers or request payloads natively, we use OkHttp's `okhttp-sse` extension and wrap it inside a Kotlin `Flow`.

### A. Stream Data Schemas
These classes map the data payloads received inside SSE chunks.

```kotlin
data class ChatStartData(
    @SerializedName("chat_id") val chatId: String,
    val title: String
)

data class ChunkData(
    val text: String
)
```

### B. Chat Request Schema
Passed as payload in `/ai/chat`.

```kotlin
data class ChatRequest(
    val prompt: String,
    val provider: String, // "claude", "openai", or "ollama"
    @SerializedName("chat_id") val chatId: String? = null,
    val model: String? = null,
    @SerializedName("character_id") val characterId: String? = null
)
```

### C. Sealed Class for Stream States
Exposes states to the presentation layer.

```kotlin
sealed class ChatStreamEvent {
    data class ChatStart(val chatId: String, val title: String) : ChatStreamEvent()
    data class Chunk(val text: String) : ChatStreamEvent()
    object Done : ChatStreamEvent()
    data class Error(val errorMsg: String) : ChatStreamEvent()
}
```

### D. Flow Event Stream Implementation
Uses `EventSource` listener to stream incoming SSE packets into a Coroutine Flow.

```kotlin
package com.openbrain.data.repository

import com.google.gson.Gson
import com.openbrain.data.local.TokenStorage
import com.openbrain.data.remote.*
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.callbackFlow
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.Response
import okhttp3.sse.EventSource
import okhttp3.sse.EventSourceListener
import okhttp3.sse.EventSources
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class AIChatRepository @Inject constructor(
    private val okHttpClient: OkHttpClient,
    private val tokenStorage: TokenStorage,
    private val gson: Gson
) {
    fun streamAIChat(chatRequest: ChatRequest): Flow<ChatStreamEvent> = callbackFlow {
        val requestJson = gson.toJson(chatRequest)
        val body = requestJson.toRequestBody("application/json".toMediaType())
        
        val request = Request.Builder()
            // Connect to local or remote endpoint
            .url("http://10.0.2.2:8000/ai/chat")
            .post(body)
            .header("Authorization", "Bearer ${tokenStorage.getAccessToken()}")
            .header("Accept", "text/event-stream")
            .build()

        val listener = object : EventSourceListener() {
            override fun onOpen(eventSource: EventSource, response: Response) {
                // Connection successfully established
            }

            override fun onEvent(eventSource: EventSource, id: String?, event: String?, data: String) {
                when (event) {
                    "chat_start" -> {
                        val startData = gson.fromJson(data, ChatStartData::class.java)
                        trySend(ChatStreamEvent.ChatStart(startData.chatId, startData.title))
                    }
                    "chunk" -> {
                        val chunkData = gson.fromJson(data, ChunkData::class.java)
                        trySend(ChatStreamEvent.Chunk(chunkData.text))
                    }
                    "done" -> {
                        trySend(ChatStreamEvent.Done)
                        close()
                    }
                }
            }

            override fun onClosed(eventSource: EventSource) {
                close()
            }

            override fun onFailure(eventSource: EventSource, t: Throwable?, response: Response?) {
                val errorMsg = t?.message ?: response?.body?.string() ?: "Stream failed"
                trySend(ChatStreamEvent.Error(errorMsg))
                close(t)
            }
        }

        val sseFactory = EventSources.createFactory(okHttpClient)
        val eventSource = sseFactory.newEventSource(request, listener)

        // Close connection immediately if the coroutine collector is cancelled
        awaitClose {
            eventSource.cancel()
        }
    }
}
```

---

## 🎨 6. ViewModel & Jetpack Compose UI Integration

To build a premium UI with a chat interface, we map the SSE stream events to a Compose State.

### A. ViewModel State Class
Contains the reactive state of the current chat UI.

```kotlin
data class ChatUiState(
    val activeChatId: String? = null,
    val conversationTitle: String = "New Chat",
    val messages: List<UiMessage> = emptyList(),
    val isStreaming: Boolean = false,
    val errorMessage: String? = null
)

data class UiMessage(
    val id: String,
    val role: String, // "user" or "assistant"
    val content: String,
    val isStreamingPlaceholder: Boolean = false
)
```

### B. ChatViewModel
Handles calling the repository and updating the UI state.

```kotlin
package com.openbrain.ui.chat

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.openbrain.data.remote.ChatRequest
import com.openbrain.data.repository.AIChatRepository
import com.openbrain.data.repository.ChatStreamEvent
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import java.util.UUID
import javax.inject.Inject

@HiltViewModel
class ChatViewModel @Inject constructor(
    private val chatRepository: AIChatRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow(ChatUiState())
    val uiState = _uiState.asStateFlow()

    fun sendMessage(promptText: String, provider: String, characterId: String?) {
        if (promptText.isBlank() || _uiState.value.isStreaming) return

        val userMessage = UiMessage(
            id = UUID.randomUUID().toString(),
            role = "user",
            content = promptText
        )

        // Optimistically append the user's message to UI list
        _uiState.update { currentState ->
            currentState.copy(
                messages = currentState.messages + userMessage,
                isStreaming = true,
                errorMessage = null
            )
        }

        viewModelScope.launch {
            chatRepository.streamAIChat(
                ChatRequest(
                    prompt = promptText,
                    provider = provider,
                    chatId = _uiState.value.activeChatId,
                    characterId = characterId
                )
            ).collect { event ->
                when (event) {
                    is ChatStreamEvent.ChatStart -> {
                        _uiState.update { it.copy(activeChatId = event.chatId, conversationTitle = event.title) }
                    }
                    is ChatStreamEvent.Chunk -> {
                        // Append token text to assistant's last message if it is currently streaming
                        _uiState.update { state ->
                            val updatedMessages = state.messages.toMutableList()
                            val lastMsg = updatedMessages.lastOrNull()

                            if (lastMsg != null && lastMsg.role == "assistant" && lastMsg.isStreamingPlaceholder) {
                                updatedMessages[updatedMessages.lastIndex] = lastMsg.copy(
                                    content = lastMsg.content + event.text
                                )
                            } else {
                                // First chunk of the AI response: create a new placeholder message
                                updatedMessages.add(
                                    UiMessage(
                                        id = UUID.randomUUID().toString(),
                                        role = "assistant",
                                        content = event.text,
                                        isStreamingPlaceholder = true
                                    )
                                )
                            }
                            state.copy(messages = updatedMessages)
                        }
                    }
                    is ChatStreamEvent.Done -> {
                        // Streaming completed; convert placeholder to permanent message
                        _uiState.update { state ->
                            val updatedMessages = state.messages.map { msg ->
                                if (msg.isStreamingPlaceholder) msg.copy(isStreamingPlaceholder = false) else msg
                            }
                            state.copy(messages = updatedMessages, isStreaming = false)
                        }
                    }
                    is ChatStreamEvent.Error -> {
                        _uiState.update { it.copy(isStreaming = false, errorMessage = event.errorMsg) }
                    }
                }
            }
        }
    }
}
```

### C. Jetpack Compose Chat Screen Example
Implement a beautiful, responsive, and state-driven chat feed screen in Compose.

```kotlin
package com.openbrain.ui.chat

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ChatScreen(
    viewModel: ChatViewModel,
    modifier: Modifier = Modifier
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()
    var textInput by remember { mutableStateOf("") }
    val listState = rememberLazyListState()

    // Auto-scroll to bottom of conversation feed on new message or new stream chunk
    LaunchedEffect(uiState.messages.size, uiState.messages.lastOrNull()?.content) {
        if (uiState.messages.isNotEmpty()) {
            listState.animateScrollToItem(uiState.messages.lastIndex)
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(uiState.conversationTitle, fontWeight = FontWeight.Bold) },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.surfaceVariant
                )
            )
        },
        bottomBar = {
            Surface(tonalElevation = 8.dp) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(8.dp)
                        .navigationBarsPadding()
                        .imePadding(),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    TextField(
                        value = textInput,
                        onValueChange = { textInput = it },
                        modifier = Modifier.weight(1f),
                        placeholder = { Text("Ask anything...") },
                        maxLines = 4,
                        colors = TextFieldDefaults.colors(
                            focusedIndicatorColor = Color.Transparent,
                            unfocusedIndicatorColor = Color.Transparent
                        ),
                        shape = RoundedCornerShape(24.dp)
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Button(
                        onClick = {
                            viewModel.sendMessage(textInput, "claude", null)
                            textInput = ""
                        },
                        enabled = textInput.isNotBlank() && !uiState.isStreaming,
                        shape = RoundedCornerShape(50)
                    ) {
                        Text("Send")
                    }
                }
            }
        },
        modifier = modifier
    ) { innerPadding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
        ) {
            if (uiState.errorMessage != null) {
                Text(
                    text = uiState.errorMessage ?: "",
                    color = MaterialTheme.colorScheme.error,
                    modifier = Modifier.padding(16.dp),
                    fontSize = 14.sp
                )
            }

            LazyColumn(
                state = listState,
                modifier = Modifier
                    .weight(1f)
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
                contentPadding = PaddingValues(vertical = 16.dp)
            ) {
                items(uiState.messages) { msg ->
                    ChatBubble(message = msg)
                }
            }
        }
    }
}

@Composable
fun ChatBubble(message: UiMessage) {
    val isUser = message.role == "user"
    val bubbleColor = if (isUser) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.secondaryContainer
    val textColor = if (isUser) MaterialTheme.colorScheme.onPrimary else MaterialTheme.colorScheme.onSecondaryContainer
    val alignment = if (isUser) Alignment.End else Alignment.Start
    val shape = if (isUser) {
        RoundedCornerShape(16.dp, 16.dp, 0.dp, 16.dp)
    } else {
        RoundedCornerShape(16.dp, 16.dp, 16.dp, 0.dp)
    }

    Column(
        modifier = Modifier.fillMaxWidth(),
        horizontalAlignment = alignment
    ) {
        Box(
            modifier = Modifier
                .clip(shape)
                .background(bubbleColor)
                .padding(horizontal = 16.dp, vertical = 10.dp)
                .widthIn(max = 280.dp)
        ) {
            Text(
                text = message.content,
                color = textColor,
                fontSize = 16.sp
            )
        }
    }
}
```

---

## ⚡ 7. Android Integration Checklist

When building out the frontend application, follow this integration checklist to ensure correct operation:

- [ ] **Configure Network Permissions:** Declare `<uses-permission android:name="android.permission.INTERNET" />` in `AndroidManifest.xml`.
- [ ] **Setup Cleartext Configuration:** Add `network_security_config.xml` to allow testing against `10.0.2.2:8000` locally without SSL.
- [ ] **Secure Storage:** Instantiate `TokenStorage` with `EncryptedSharedPreferences` for access and refresh tokens.
- [ ] **Verify Authentication Interceptors:** Verify the `AuthInterceptor` attaches `Bearer` tokens and `TokenAuthenticator` initiates sync refreshes.
- [ ] **Map SSE Flow:** Ensure that your SSE listener closes the flow connection inside `awaitClose` to prevent background network leaks.
- [ ] **Design State Machine:** Ensure UI screens map state variables (`isStreaming`, messages) cleanly to prevent duplicate rendering or sluggish scroll performance.
