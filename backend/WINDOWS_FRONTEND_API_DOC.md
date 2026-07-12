# 💻 Open-Brain Windows Frontend Integration & API Documentation

This document serves as the official API integration guide and specifications for Windows desktop app developers building the Open-Brain client. It covers network configuration, architectural design using C# / .NET 8 (WPF, WinUI 3, or MAUI), JWT/MFA authentication flows, secure credential storage, and consumption of Server-Sent Event (SSE) AI streams using `IAsyncEnumerable`.

---

## 🗺️ 1. Networking & Local Development Setup

When developing the Windows desktop application locally against a FastAPI backend, the network configuration is straightforward.

### A. Endpoint Resolution
* **Local Development:** Unlike Android emulators, a Windows desktop app runs natively on the host machine and can access the backend directly via `localhost` or `127.0.0.1`.
  * **Base URL:** `http://localhost:8000`
* **Production / Remote Development:** Connects to the public HTTPS URL exposed by the **Cloudflare Tunnel**.
  * **Base URL:** `https://your-cloudflare-subdomain.trycloudflare.com`

### B. Network Exceptions & Proxy Settings
Windows applications honor system-wide proxy settings automatically. However, ensure that your local firewall allows outbound traffic on port `8000` if the backend is hosted on a different device on the local network.

---

## 🏗️ 2. Architectural Design & Project Configuration

For Windows native apps, we recommend using the **Model-View-ViewModel (MVVM)** pattern. You can use standard modern .NET libraries such as the **CommunityToolkit.Mvvm** for reactive bindings and **Microsoft.Extensions.DependencyInjection** for Dependency Injection.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           PRESENTATION LAYER                            │
│                  XAML UI (WinUI 3 / WPF Window / Page)                  │
│                                   ▲                                     │
│                                   │ (Data Binding via ObservableProperty)│
│            ViewModels (CommunityToolkit.Mvvm / State machine)           │
└───────────────────────────────────┬─────────────────────────────────────┘
                                    │
                                    ▼ (Calls Service Layer)
┌─────────────────────────────────────────────────────────────────────────┐
│                                DATA LAYER                               │
│        Repositories / Services (Manages HttpClient & API contracts)     │
│           ┌───────────────────────┴───────────────────────┐             │
│           ▼ (REST API calls over HTTP)                    ▼ (Local Storage)│
│     HttpClient & DelegatingHandlers               Windows Credential    │
│     (Auth & Token Rotation)                       Manager / DPAPI       │
└─────────────────────────────────────────────────────────────────────────┘
```

### Required NuGet Packages (`.csproj`)
Ensure the following packages are referenced in your C# project file:

```xml
<ItemGroup>
  <!-- HTTP & JSON Serialization -->
  <PackageReference Include="System.Net.Http" Version="4.3.4" />
  <PackageReference Include="System.Text.Json" Version="8.0.3" />

  <!-- MVVM Toolkit & Dependency Injection -->
  <PackageReference Include="CommunityToolkit.Mvvm" Version="8.2.2" />
  <PackageReference Include="Microsoft.Extensions.DependencyInjection" Version="8.0.0" />

  <!-- Windows Credential Manager Helper -->
  <PackageReference Include="CredentialManagement" Version="1.0.2" />
</ItemGroup>
```

---

## 🔐 3. Authentication & Session Management

The client app needs to securely store JWT credentials (`access_token`, `refresh_token`) and automatically refresh expired access tokens.

```
                    ┌────────────────────────────────────────┐
                    │          Windows Secure Store          │
                    │   Windows Credential Manager / DPAPI   │
                    └───────────────────┬────────────────────┘
                                        │
                                        ▼ (Provide tokens / Check expiry)
                      ┌──────────────────────────────────┐
                      │    HttpClient DelegatingHandlers │
                      └────────────────┬─────────────────┘
                                       │
            ┌──────────────────────────┴──────────────────────────┐
            ▼                                                     ▼
┌────────────────────────┐                             ┌────────────────────────┐
│ AuthHeaderHandler      │                             │ TokenRefreshHandler    │
│ Automatically appends  │                             │ Intercepts 401s,       │
│ "Authorization: Bearer"│                             │ sends POST /auth/refresh│
│ to requests.           │                             │ & retries transparently│
└────────────────────────┘                             └────────────────────────┘
```

### A. Secure Token Storage Implementation
Use the Windows Credential Manager or DPAPI (Data Protection API) to store sensitive JWT tokens.

```csharp
using System;
using System.Text;
using System.Security.Cryptography;
using CredentialManagement;

namespace OpenBrain.Data.Local
{
    public interface ITokenStorage
    {
        void SaveTokens(string accessToken, string refreshToken);
        string GetAccessToken();
        string GetRefreshToken();
        void ClearTokens();
    }

    public class WindowsTokenStorage : ITokenStorage
    {
        private const string AccessTokenKey = "OpenBrain:AccessToken";
        private const string RefreshTokenTarget = "OpenBrain:RefreshToken";

        // Store Access Token encrypted with DPAPI (User-specific scope)
        public void SaveTokens(string accessToken, string refreshToken)
        {
            byte[] accessBytes = Encoding.UTF8.GetBytes(accessToken);
            byte[] encryptedAccess = ProtectedData.Protect(accessBytes, null, DataProtectionScope.CurrentUser);
            string base64Access = Convert.ToBase64String(encryptedAccess);

            // Store in user profile environment or local app registry
            Environment.SetEnvironmentVariable(AccessTokenKey, base64Access, EnvironmentVariableTarget.User);

            // Store Refresh Token in Windows Credential Manager
            using (var cred = new Credential { Target = RefreshTokenTarget })
            {
                cred.Username = "OpenBrainSession";
                cred.Password = refreshToken;
                cred.PersistanceType = PersistanceType.LocalComputer;
                cred.Save();
            }
        }

        public string GetAccessToken()
        {
            try
            {
                var base64Access = Environment.GetEnvironmentVariable(AccessTokenKey, EnvironmentVariableTarget.User);
                if (string.IsNullOrEmpty(base64Access)) return null;

                byte[] encryptedAccess = Convert.FromBase64String(base64Access);
                byte[] decryptedAccess = ProtectedData.Unprotect(encryptedAccess, null, DataProtectionScope.CurrentUser);
                return Encoding.UTF8.GetString(decryptedAccess);
            }
            catch
            {
                return null;
            }
        }

        public string GetRefreshToken()
        {
            using (var cred = new Credential { Target = RefreshTokenTarget })
            {
                if (cred.Load())
                {
                    return cred.Password;
                }
            }
            return null;
        }

        public void ClearTokens()
        {
            Environment.SetEnvironmentVariable(AccessTokenKey, null, EnvironmentVariableTarget.User);
            using (var cred = new Credential { Target = RefreshTokenTarget })
            {
                cred.Delete();
            }
        }
    }
}
```

### B. Transparent Token Rotation Delegating Handler
This handler automatically injects bearer tokens and handles silent token refresh calls when HTTP `401 Unauthorized` is encountered.

```csharp
using System;
using System.Net;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using OpenBrain.Data.Local;
using OpenBrain.Data.Remote.Dtos;

namespace OpenBrain.Data.Remote
{
    public class TokenRefreshHandler : DelegatingHandler
    {
        private readonly ITokenStorage _tokenStorage;
        private readonly string _baseUrl;
        private static readonly SemaphoreSlim TokenSemaphore = new SemaphoreSlim(1, 1);

        public TokenRefreshHandler(ITokenStorage tokenStorage, string baseUrl)
        {
            _tokenStorage = tokenStorage;
            _baseUrl = baseUrl;
        }

        protected override async Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
        {
            // 1. Attach current access token
            var accessToken = _tokenStorage.GetAccessToken();
            if (!string.IsNullOrEmpty(accessToken))
            {
                request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", accessToken);
            }

            var response = await base.SendAsync(request, cancellationToken);

            // 2. Intercept 401 Unauthorized errors
            if (response.StatusCode == HttpStatusCode.Unauthorized)
            {
                await TokenSemaphore.WaitAsync(cancellationToken);
                try
                {
                    // Verify if another concurrent request already refreshed the token
                    var latestAccessToken = _tokenStorage.GetAccessToken();
                    if (latestAccessToken != accessToken)
                    {
                        // Retry request with the newly rotated token
                        request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", latestAccessToken);
                        return await base.SendAsync(request, cancellationToken);
                    }

                    // Otherwise, trigger refresh flow
                    var refreshed = await RefreshTokensAsync();
                    if (refreshed)
                    {
                        var newAccess = _tokenStorage.GetAccessToken();
                        request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", newAccess);
                        return await base.SendAsync(request, cancellationToken);
                    }
                    else
                    {
                        // Token refresh failed or session revoked: log out user
                        _tokenStorage.ClearTokens();
                        TriggerLogout();
                    }
                }
                finally
                {
                    TokenSemaphore.Release();
                }
            }

            return response;
        }

        private async Task<bool> RefreshTokensAsync()
        {
            var refreshToken = _tokenStorage.GetRefreshToken();
            if (string.IsNullOrEmpty(refreshToken)) return false;

            using (var client = new HttpClient())
            {
                var refreshRequest = new HttpRequestMessage(HttpMethod.Post, $"{_baseUrl}/auth/refresh");
                refreshRequest.Headers.Authorization = new AuthenticationHeaderValue("Bearer", refreshToken);

                try
                {
                    var response = await client.SendAsync(refreshRequest);
                    if (response.IsSuccessStatusCode)
                    {
                        var content = await response.Content.ReadAsStringAsync();
                        var tokens = JsonSerializer.Deserialize<TokenResponseDto>(content, new JsonSerializerOptions
                        {
                            PropertyNameCaseInsensitive = true
                        });

                        if (tokens != null)
                        {
                            _tokenStorage.SaveTokens(tokens.AccessToken, tokens.RefreshToken);
                            return true;
                        }
                    }
                }
                catch
                {
                    // Log error / Network issues
                }
            }
            return false;
        }

        private void TriggerLogout()
        {
            // Trigger a global UI logout event or publish to EventAggregator
        }
    }
}
```

---

## 📦 4. Data Transfer Objects (DTOs) & API Client

### A. C# Data Transfer Objects
Map the FastAPI Pydantic requests/responses directly to C# record or class types.

```csharp
using System.Text.Json.Serialization;

namespace OpenBrain.Data.Remote.Dtos
{
    // --- Auth DTOs ---
    public record RegisterInitiateRequest(
        [property: JsonPropertyName("email")] string Email,
        [property: JsonPropertyName("password")] string Password
    );

    public record RegisterInitiateResponse(
        [property: JsonPropertyName("registration_token")] string RegistrationToken,
        [property: JsonPropertyName("message")] string Message
    );

    public record RegisterVerifyRequest(
        [property: JsonPropertyName("registration_token")] string RegistrationToken,
        [property: JsonPropertyName("email")] string Email,
        [property: JsonPropertyName("otp")] string Otp
    );

    public record LoginRequest(
        [property: JsonPropertyName("email")] string Email,
        [property: JsonPropertyName("password")] string Password
    );

    public record LoginMFAChallengeResponse(
        [property: JsonPropertyName("otp_required")] bool OtpRequired,
        [property: JsonPropertyName("mfa_token")] string MfaToken,
        [property: JsonPropertyName("email")] string Email
    );

    public record VerifyLoginOTPRequest(
        [property: JsonPropertyName("mfa_token")] string MfaToken,
        [property: JsonPropertyName("otp")] string Otp
    );

    public record TokenResponseDto(
        [property: JsonPropertyName("access_token")] string AccessToken,
        [property: JsonPropertyName("refresh_token")] string RefreshToken,
        [property: JsonPropertyName("token_type")] string TokenType
    );

    // --- Folder DTOs ---
    public record FolderDto(
        [property: JsonPropertyName("id")] string Id,
        [property: JsonPropertyName("name")] string Name,
        [property: JsonPropertyName("created_at")] string CreatedAt
    );

    public record CreateFolderRequest(
        [property: JsonPropertyName("name")] string Name
    );

    // --- Attachment DTOs ---
    public record AttachmentDto(
        [property: JsonPropertyName("id")] string Id,
        [property: JsonPropertyName("filename")] string Filename,
        [property: JsonPropertyName("content_type")] string ContentType,
        [property: JsonPropertyName("size_bytes")] long SizeBytes,
        [property: JsonPropertyName("url")] string Url
    );

    // --- Billing DTOs ---
    public record BillingPlanDto(
        [property: JsonPropertyName("id")] string Id,
        [property: JsonPropertyName("name")] string Name,
        [property: JsonPropertyName("price")] int Price,
        [property: JsonPropertyName("currency")] string Currency
    );

    public record SubscribeRequest(
        [property: JsonPropertyName("plan_id")] string PlanId
    );

    public record CheckoutResponse(
        [property: JsonPropertyName("checkout_url")] string CheckoutUrl
    );

    public record InvoiceDto(
        [property: JsonPropertyName("id")] string Id,
        [property: JsonPropertyName("amount")] int Amount,
        [property: JsonPropertyName("date")] string Date,
        [property: JsonPropertyName("pdf_url")] string PdfUrl
    );

    // --- Notification & Support DTOs ---
    public record NotificationDto(
        [property: JsonPropertyName("id")] string Id,
        [property: JsonPropertyName("title")] string Title,
        [property: JsonPropertyName("message")] string Message,
        [property: JsonPropertyName("read")] bool Read
    );

    public record SupportRequestDto(
        [property: JsonPropertyName("name")] string Name,
        [property: JsonPropertyName("email")] string Email,
        [property: JsonPropertyName("message")] string Message
    );

    // --- Admin DTOs ---
    public record AdminStatsDto(
        [property: JsonPropertyName("total_users")] int TotalUsers,
        [property: JsonPropertyName("premium_users")] int PremiumUsers,
        [property: JsonPropertyName("total_messages")] int TotalMessages,
        [property: JsonPropertyName("total_revenue")] int TotalRevenue
    );

    // --- User Profiles ---
    public record UserProfileResponse(
        [property: JsonPropertyName("id")] string Id,
        [property: JsonPropertyName("email")] string Email,
        [property: JsonPropertyName("is_verified")] bool IsVerified,
        [property: JsonPropertyName("plan")] string Plan,
        [property: JsonPropertyName("created_at")] string CreatedAt
    );

    // --- Chat Histories ---
    public record ConversationListItem(
        [property: JsonPropertyName("chat_id")] string ChatId,
        [property: JsonPropertyName("title")] string Title,
        [property: JsonPropertyName("updated_at")] string UpdatedAt
    );

    public record PaginatedConversationsResponse(
        [property: JsonPropertyName("conversations")] ConversationListItem[] Conversations,
        [property: JsonPropertyName("total")] int Total,
        [property: JsonPropertyName("page")] int Page,
        [property: JsonPropertyName("page_size")] int PageSize,
        [property: JsonPropertyName("has_next")] bool HasNext
    );

    public record MessageSchema(
        [property: JsonPropertyName("id")] string Id,
        [property: JsonPropertyName("role")] string Role, // "user" or "assistant"
        [property: JsonPropertyName("content")] string Content,
        [property: JsonPropertyName("provider_used")] string ProviderUsed,
        [property: JsonPropertyName("token_count")] int? TokenCount,
        [property: JsonPropertyName("is_partial")] bool IsPartial,
        [property: JsonPropertyName("created_at")] string CreatedAt
    );

    public record ConversationHistoryResponse(
        [property: JsonPropertyName("chat_id")] string ChatId,
        [property: JsonPropertyName("title")] string Title,
        [property: JsonPropertyName("messages")] MessageSchema[] Messages,
        [property: JsonPropertyName("created_at")] string CreatedAt,
        [property: JsonPropertyName("updated_at")] string UpdatedAt
    );

    // --- AI Personas ---
    public record CharacterSchema(
        [property: JsonPropertyName("id")] string Id,
        [property: JsonPropertyName("name")] string Name,
        [property: JsonPropertyName("description")] string Description,
        [property: JsonPropertyName("system_prompt")] string SystemPrompt,
        [property: JsonPropertyName("avatar")] string Avatar
    );

    // --- Core Generic Responses ---
    public record MessageResponse(
        [property: JsonPropertyName("message")] string Message
    );
}
```

### B. Open-Brain API Client Service
A service managing client REST requests.

```csharp
using System.Net.Http;
using System.Net.Http.Json;
using System.Threading.Tasks;
using OpenBrain.Data.Remote.Dtos;

namespace OpenBrain.Data.Remote
{
    public class OpenBrainApiClient
    {
        private readonly HttpClient _client;

        public OpenBrainApiClient(HttpClient client)
        {
            _client = client;
        }

        // --- Auth Operations ---

        public async Task<RegisterInitiateResponse> RegisterInitiateAsync(string email, string password)
        {
            var res = await _client.PostAsJsonAsync("/auth/register/send-otp", new RegisterInitiateRequest(email, password));
            res.EnsureSuccessStatusCode();
            return await res.Content.ReadFromJsonAsync<RegisterInitiateResponse>();
        }

        public async Task<TokenResponseDto> RegisterVerifyAsync(string registrationToken, string email, string otp)
        {
            var res = await _client.PostAsJsonAsync("/auth/register", new RegisterVerifyRequest(registrationToken, email, otp));
            res.EnsureSuccessStatusCode();
            return await res.Content.ReadFromJsonAsync<TokenResponseDto>();
        }

        public async Task<LoginMFAChallengeResponse> LoginInitiateAsync(string email, string password)
        {
            var res = await _client.PostAsJsonAsync("/auth/login", new LoginRequest(email, password));
            res.EnsureSuccessStatusCode();
            return await res.Content.ReadFromJsonAsync<LoginMFAChallengeResponse>();
        }

        public async Task<TokenResponseDto> LoginVerifyAsync(string mfaToken, string otp)
        {
            var res = await _client.PostAsJsonAsync("/auth/login/verify", new VerifyLoginOTPRequest(mfaToken, otp));
            res.EnsureSuccessStatusCode();
            return await res.Content.ReadFromJsonAsync<TokenResponseDto>();
        }

        public async Task LogoutAsync()
        {
            var res = await _client.PostAsync("/auth/logout", null);
            res.EnsureSuccessStatusCode();
        }

        // --- Folders ---
        public async Task<FolderDto[]> GetFoldersAsync()
        {
            return await _client.GetFromJsonAsync<FolderDto[]>("/folders");
        }

        public async Task<FolderDto> CreateFolderAsync(string name)
        {
            var res = await _client.PostAsJsonAsync("/folders", new CreateFolderRequest(name));
            res.EnsureSuccessStatusCode();
            return await res.Content.ReadFromJsonAsync<FolderDto>();
        }

        public async Task<FolderDto> RenameFolderAsync(string folderId, string name)
        {
            var res = await _client.PatchAsJsonAsync($"/folders/{folderId}", new CreateFolderRequest(name));
            res.EnsureSuccessStatusCode();
            return await res.Content.ReadFromJsonAsync<FolderDto>();
        }

        public async Task DeleteFolderAsync(string folderId)
        {
            var res = await _client.DeleteAsync($"/folders/{folderId}");
            res.EnsureSuccessStatusCode();
        }

        // --- Attachments ---
        public async Task<AttachmentDto> UploadAttachmentAsync(string chatId, byte[] fileBytes, string filename, string contentType)
        {
            using var content = new MultipartFormDataContent();
            using var fileContent = new ByteArrayContent(fileBytes);
            fileContent.Headers.ContentType = new System.Net.Http.Headers.MediaTypeHeaderValue(contentType);
            content.Add(fileContent, "file", filename);
            var res = await _client.PostAsync($"/chats/{chatId}/attachments", content);
            res.EnsureSuccessStatusCode();
            return await res.Content.ReadFromJsonAsync<AttachmentDto>();
        }

        public async Task<System.IO.Stream> DownloadAttachmentAsync(string attachmentId)
        {
            return await _client.GetStreamAsync($"/attachments/{attachmentId}");
        }

        public async Task DeleteAttachmentAsync(string attachmentId)
        {
            var res = await _client.DeleteAsync($"/attachments/{attachmentId}");
            res.EnsureSuccessStatusCode();
        }

        // --- Billing ---
        public async Task<BillingPlanDto[]> GetBillingPlansAsync()
        {
            return await _client.GetFromJsonAsync<BillingPlanDto[]>("/billing/plans");
        }

        public async Task<CheckoutResponse> SubscribeAsync(string planId)
        {
            var res = await _client.PostAsJsonAsync("/billing/subscribe", new SubscribeRequest(planId));
            res.EnsureSuccessStatusCode();
            return await res.Content.ReadFromJsonAsync<CheckoutResponse>();
        }

        public async Task CancelSubscriptionAsync()
        {
            var res = await _client.PostAsync("/billing/cancel", null);
            res.EnsureSuccessStatusCode();
        }

        public async Task<InvoiceDto[]> GetInvoicesAsync()
        {
            return await _client.GetFromJsonAsync<InvoiceDto[]>("/billing/invoices");
        }

        // --- Notifications ---
        public async Task<NotificationDto[]> GetNotificationsAsync()
        {
            return await _client.GetFromJsonAsync<NotificationDto[]>("/notifications");
        }

        public async Task<NotificationDto> MarkNotificationReadAsync(string id)
        {
            var res = await _client.PatchAsync($"/notifications/{id}/read", null);
            res.EnsureSuccessStatusCode();
            return await res.Content.ReadFromJsonAsync<NotificationDto>();
        }

        // --- Support ---
        public async Task SubmitSupportRequestAsync(string name, string email, string message)
        {
            var res = await _client.PostAsJsonAsync("/support/contact", new SupportRequestDto(name, email, message));
            res.EnsureSuccessStatusCode();
        }

        // --- Admin ---
        public async Task<AdminStatsDto> GetAdminStatsAsync()
        {
            return await _client.GetFromJsonAsync<AdminStatsDto>("/admin/stats");
        }

        // --- Profiles ---

        public async Task<UserProfileResponse> GetUserProfileAsync()
        {
            return await _client.GetFromJsonAsync<UserProfileResponse>("/users/me");
        }

        // --- Conversations ---

        public async Task<PaginatedConversationsResponse> GetChatsAsync(int page = 1, int pageSize = 20)
        {
            return await _client.GetFromJsonAsync<PaginatedConversationsResponse>($"/chats?page={page}&page_size={pageSize}");
        }

        public async Task<ConversationHistoryResponse> GetChatHistoryAsync(string chatId)
        {
            return await _client.GetFromJsonAsync<ConversationHistoryResponse>($"/chats/{chatId}/history");
        }

        public async Task DeleteChatAsync(string chatId)
        {
            var res = await _client.DeleteAsync($"/chats/{chatId}");
            res.EnsureSuccessStatusCode();
        }

        // --- Characters ---

        public async Task<CharacterSchema[]> GetCharactersAsync()
        {
            return await _client.GetFromJsonAsync<CharacterSchema[]>("/ai/characters");
        }
    }
}
```

---

## 🤖 5. Consuming Server-Sent Events (SSE) AI Streams

FastAPI streams token updates using Server-Sent Events (SSE) over a POST request. In .NET, we read the response stream directly chunk-by-chunk and yields tokens as an `IAsyncEnumerable<ChatStreamEvent>`.

### A. Stream Types
Define representing classes for stream structures.

```csharp
using System.Text.Json.Serialization;

namespace OpenBrain.Data.Remote.Dtos
{
    public record ChatRequest(
        [property: JsonPropertyName("prompt")] string Prompt,
        [property: JsonPropertyName("provider")] string Provider,
        [property: JsonPropertyName("chat_id")] string ChatId = null,
        [property: JsonPropertyName("model")] string Model = null,
        [property: JsonPropertyName("character_id")] string CharacterId = null
    );

    public record ChatStartData(
        [property: JsonPropertyName("chat_id")] string ChatId,
        [property: JsonPropertyName("title")] string Title
    );

    public record ChunkData(
        [property: JsonPropertyName("text")] string Text
    );

    public abstract record ChatStreamEvent
    {
        public record ChatStart(string ChatId, string Title) : ChatStreamEvent;
        public record Chunk(string Text) : ChatStreamEvent;
        public record Done : ChatStreamEvent;
        public record Error(string Message) : ChatStreamEvent;
    }
}
```

### B. Streaming Implementation
Reads the raw HTTP stream line-by-line using `StreamReader`.

```csharp
using System;
using System.IO;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Runtime.CompilerServices;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using OpenBrain.Data.Remote.Dtos;

namespace OpenBrain.Data.Remote
{
    public class AIChatStreamService
    {
        private readonly HttpClient _client;

        public AIChatStreamService(HttpClient client)
        {
            _client = client;
        }

        public async IAsyncEnumerable<ChatStreamEvent> StreamAIChatAsync(
            ChatRequest request, 
            [EnumeratorCancellation] CancellationToken cancellationToken = default)
        {
            var requestMessage = new HttpRequestMessage(HttpMethod.Post, "/ai/chat")
            {
                Content = JsonContent.Create(request)
            };
            requestMessage.Headers.Accept.Add(new MediaTypeWithQualityHeaderValue("text/event-stream"));

            HttpResponseMessage response;
            try
            {
                // Force headers to resolve quickly, then stream the content body
                response = await _client.SendAsync(requestMessage, HttpCompletionOption.ResponseHeadersRead, cancellationToken);
                response.EnsureSuccessStatusCode();
            }
            catch (Exception ex)
            {
                yield return new ChatStreamEvent.Error(ex.Message);
                yield break;
            }

            using (var stream = await response.Content.ReadAsStreamAsync(cancellationToken))
            using (var reader = new StreamReader(stream))
            {
                string currentEventName = null;

                while (!reader.EndOfStream && !cancellationToken.IsCancellationRequested)
                {
                    var line = await reader.ReadLineAsync(cancellationToken);
                    if (string.IsNullOrWhiteSpace(line)) continue;

                    // Parse Event Name (e.g., "event: chunk")
                    if (line.StartsWith("event:"))
                    {
                        currentEventName = line.Substring(6).Trim();
                        continue;
                    }

                    // Parse Event Data (e.g., "data: {"text": " hello"}")
                    if (line.StartsWith("data:") && currentEventName != null)
                    {
                        var dataJson = line.Substring(5).Trim();
                        ChatStreamEvent streamEvent = null;

                        try
                        {
                            switch (currentEventName)
                            {
                                case "chat_start":
                                    var start = JsonSerializer.Deserialize<ChatStartData>(dataJson);
                                    if (start != null) streamEvent = new ChatStreamEvent.ChatStart(start.ChatId, start.Title);
                                    break;

                                case "chunk":
                                    var chunk = JsonSerializer.Deserialize<ChunkData>(dataJson);
                                    if (chunk != null) streamEvent = new ChatStreamEvent.Chunk(chunk.Text);
                                    break;

                                case "done":
                                    streamEvent = new ChatStreamEvent.Done();
                                    break;
                            }
                        }
                        catch (Exception ex)
                        {
                            streamEvent = new ChatStreamEvent.Error($"JSON parsing exception: {ex.Message}");
                        }

                        if (streamEvent != null)
                        {
                            yield return streamEvent;
                        }

                        currentEventName = null; // Reset event for next iteration
                    }
                }
            }
        }
    }
}
```

---

## 🎨 6. MVVM & WinUI 3 Presentation Integration

This section shows how to consume the `IAsyncEnumerable` stream inside your ViewModel and update your Windows UI (using the MVVM Toolkit).

### A. ViewModel Message Model
```csharp
using CommunityToolkit.Mvvm.ComponentModel;

namespace OpenBrain.Presentation.Models
{
    public partial class UiMessage : ObservableObject
    {
        public string Id { get; set; }
        public string Role { get; set; } // "user" or "assistant"

        [ObservableProperty]
        private string _content;

        public bool IsStreamingPlaceholder { get; set; }
    }
}
```

### B. ChatViewModel
```csharp
using System;
using System.Collections.ObjectModel;
using System.Threading;
using System.Threading.Tasks;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using OpenBrain.Data.Remote;
using OpenBrain.Data.Remote.Dtos;
using OpenBrain.Presentation.Models;

namespace OpenBrain.Presentation.ViewModels
{
    public partial class ChatViewModel : ObservableObject
    {
        private readonly AIChatStreamService _streamService;
        private CancellationTokenSource _streamCts;

        [ObservableProperty]
        private string _activeChatId;

        [ObservableProperty]
        private string _conversationTitle = "New Chat";

        [ObservableProperty]
        private bool _isStreaming;

        [ObservableProperty]
        private string _errorMessage;

        public ObservableCollection<UiMessage> Messages { get; } = new ObservableCollection<UiMessage>();

        public ChatViewModel(AIChatStreamService streamService)
        {
            _streamService = streamService;
        }

        [RelayCommand]
        public async Task SendMessageAsync(string promptText)
        {
            if (string.IsNullOrWhiteSpace(promptText) || IsStreaming) return;

            ErrorMessage = null;
            IsStreaming = true;

            // Append User message
            Messages.Add(new UiMessage
            {
                Id = Guid.NewGuid().ToString(),
                Role = "user",
                Content = promptText
            });

            _streamCts = new CancellationTokenSource();

            try
            {
                var request = new ChatRequest(
                    Prompt: promptText,
                    Provider: "claude",
                    ChatId: ActiveChatId
                );

                UiMessage assistantMessage = null;

                await foreach (var ev in _streamService.StreamAIChatAsync(request, _streamCts.Token))
                {
                    switch (ev)
                    {
                        case ChatStreamEvent.ChatStart start:
                            ActiveChatId = start.ChatId;
                            ConversationTitle = start.Title;
                            break;

                        case ChatStreamEvent.Chunk chunk:
                            if (assistantMessage == null)
                            {
                                assistantMessage = new UiMessage
                                    { Id = Guid.NewGuid().ToString(), Role = "assistant", Content = chunk.Text, IsStreamingPlaceholder = true };
                                Messages.Add(assistantMessage);
                            }
                            else
                            {
                                assistantMessage.Content += chunk.Text;
                            }
                            break;

                        case ChatStreamEvent.Done:
                            if (assistantMessage != null) assistantMessage.IsStreamingPlaceholder = false;
                            IsStreaming = false;
                            break;

                        case ChatStreamEvent.Error err:
                            ErrorMessage = err.Message;
                            IsStreaming = false;
                            break;
                    }
                }
            }
            catch (OperationCanceledException)
            {
                // Streaming was cancelled by user
            }
            finally
            {
                IsStreaming = false;
            }
        }

        [RelayCommand]
        public void CancelStream()
        {
            _streamCts?.Cancel();
            IsStreaming = false;
        }
    }
}
```

### C. WinUI 3 XAML Chat Control Example
A beautiful XAML markup using Windows App SDK layout systems.

```xml
<UserControl
    x:Class="OpenBrain.Presentation.Views.ChatView"
    xmlns="http://schemas.microsoft.com/winfx/2000/xaml/presentation"
    xmlns:x="http://schemas.microsoft.com/winfx/2000/xaml"
    xmlns:models="using:OpenBrain.Presentation.Models"
    xmlns:d="http://schemas.microsoft.com/expression/blend/2008"
    xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006"
    mc:Ignorable="d">

    <Grid RowDefinitions="Auto, *, Auto" Background="{ThemeResource ApplicationPageBackgroundThemeBrush}">
        <!-- Header -->
        <Border Grid.Row="0" Background="{ThemeResource SystemControlBackgroundChromeMediumBrush}" Padding="16,12">
            <TextBlock Text="{x:Bind ViewModel.ConversationTitle, Mode=OneWay}" FontSize="18" FontWeight="SemiBold"/>
        </Border>

        <!-- Message List -->
        <ListView Grid.Row="1" ItemsSource="{x:Bind ViewModel.Messages}" SelectionMode="None" Padding="16">
            <ListView.ItemTemplate>
                <DataTemplate x:DataType="models:UiMessage">
                    <Grid Margin="0,4" HorizontalAlignment="{x:Bind Role, Converter={StaticResource RoleToAlignmentConverter}}">
                        <Border CornerRadius="8" Padding="12,8"
                                Background="{x:Bind Role, Converter={StaticResource RoleToBackgroundConverter}}">
                            <TextBlock Text="{x:Bind Content, Mode=OneWay}" TextWrapping="Wrap" MaxWidth="450"
                                       Foreground="{x:Bind Role, Converter={StaticResource RoleToForegroundConverter}}"/>
                        </Border>
                    </Grid>
                </DataTemplate>
            </ListView.ItemTemplate>
        </ListView>

        <!-- Input Panel -->
        <Border Grid.Row="2" Padding="16" Background="{ThemeResource SystemControlBackgroundChromeMediumBrush}">
            <Grid ColumnDefinitions="*, Auto">
                <TextBox x:Name="InputBox" Grid.Column="0" PlaceholderText="Type a message..." Margin="0,0,8,0"
                         AcceptsReturn="True" MaxHeight="100"/>
                <Button Grid.Column="1" Content="Send" 
                        Command="{x:Bind ViewModel.SendMessageCommand}" 
                        CommandParameter="{Binding ElementName=InputBox, Path=Text}"
                        IsEnabled="{x:Bind ViewModel.IsStreaming, Converter={StaticResource InverseBoolConverter}, Mode=OneWay}"/>
            </Grid>
        </Border>
    </Grid>
</UserControl>
```

*(Note: Provide custom ValueConverters like `RoleToAlignmentConverter` and `RoleToBackgroundConverter` to swap alignments and theme brushes based on whether `Role == "user"`).*

---

## ⚡ 7. Windows Integration Checklist

- [ ] **Configure Target Hostname:** Declare the target base URL in `appsettings.json` or config profiles.
- [ ] **Import Security Cryptography:** Reference `System.Security.Cryptography.ProtectedData` in your `.csproj` to secure authentication tokens.
- [ ] **Configure Message Handlers:** Build the `HttpClient` pipeline using the `TokenRefreshHandler` nested within your DI setup:
  ```csharp
  services.AddHttpClient<OpenBrainApiClient>(c => c.BaseAddress = new Uri("http://localhost:8000"))
          .AddHttpMessageHandler<TokenRefreshHandler>();
  ```
- [ ] **Handle Cancellations:** Pass a `CancellationToken` to all `StreamAIChatAsync` invocations so the network stream closes immediately if a user changes tabs or navigates away.
- [ ] **Implement Value Converters:** Ensure custom converters are defined in XAML Resources to handle visual formatting of user versus assistant messages.
