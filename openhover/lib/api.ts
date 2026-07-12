import { API_BASE_URL } from "./constants"
import { getSettings } from "./storage"

export interface ExplainParams {
  text: string
  context: string
  url: string
  title: string
  provider?: string
  model?: string
}

export interface ChatMessage {
  role: "user" | "assistant" | "system"
  content: string
}

export interface ChatParams {
  messages: ChatMessage[]
  context: string
  url: string
  title: string
  provider?: string
  model?: string
  chat_id?: string
}

export interface SSEEvent {
  type: "chunk" | "done" | "error"
  content?: string
  message?: string
}

export async function explainText(
  params: ExplainParams,
  callbacks: {
    onChatStart?: (chatId: string) => void
    onChunk: (text: string) => void
    onDone: (fullText: string) => void
    onError: (error: string) => void
  }
): Promise<AbortController> {
  const controller = new AbortController()
  const settings = await getSettings()
  const payload = { ...params, provider: settings.provider, model: settings.model }

  try {
    const response = await fetch(`${API_BASE_URL}/api/explain`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": settings.accessToken ? `Bearer ${settings.accessToken}` : "",
      },
      body: JSON.stringify(payload),
      signal: controller.signal,
    })

    if (!response.ok) {
      if (response.status === 429) {
        callbacks.onError("Rate limit exceeded. Please wait a moment and try again.")
        return controller
      }
      callbacks.onError(`API error: ${response.status} ${response.statusText}`)
      return controller
    }

    const reader = response.body?.getReader()
    if (!reader) {
      callbacks.onError("No response body")
      return controller
    }

    const decoder = new TextDecoder()
    let fullText = ""
    let buffer = ""

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split("\n")
      buffer = lines.pop() || ""

      for (const line of lines) {
        if (line.startsWith("data: ")) {
          const dataStr = line.slice(6).trim()
          if (!dataStr) continue
          
          try {
            const data: SSEEvent = JSON.parse(dataStr)
            
            if (data.type === "chunk" && data.content) {
              fullText += data.content
              callbacks.onChunk(data.content)
            } else if (data.type === "done") {
              callbacks.onDone(fullText)
            } else if (data.type === "error") {
              callbacks.onError(data.message || "Unknown error")
            }
          } catch {
            // Ignore malformed JSON lines
          }
        }
      }
    }

    if (fullText.length > 0) {
      callbacks.onDone(fullText)
    }
  } catch (error) {
    if ((error as Error).name !== "AbortError") {
      callbacks.onError(error instanceof Error ? error.message : "Network error")
    }
  }

  return controller
}

export async function sendChatMessage(
  params: ChatParams,
  callbacks: {
    onChatStart?: (chatId: string) => void
    onChunk: (text: string) => void
    onDone: (fullText: string) => void
    onError: (error: string) => void
  }
): Promise<AbortController> {
  const controller = new AbortController()
  const settings = await getSettings()
  // Clean up params and add provider
  const { chat_id, ...restParams } = params
  const payload = { ...restParams, provider: settings.provider, model: settings.model }

  try {
    const response = await fetch(`${API_BASE_URL}/api/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": settings.accessToken ? `Bearer ${settings.accessToken}` : "",
      },
      body: JSON.stringify(payload),
      signal: controller.signal,
    })

    if (!response.ok) {
      if (response.status === 429) {
        callbacks.onError("Rate limit exceeded. Please wait a moment and try again.")
        return controller
      }
      callbacks.onError(`API error: ${response.status} ${response.statusText}`)
      return controller
    }

    const reader = response.body?.getReader()
    if (!reader) {
      callbacks.onError("No response body")
      return controller
    }

    const decoder = new TextDecoder()
    let fullText = ""
    let buffer = ""

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split("\n")
      buffer = lines.pop() || ""

      for (const line of lines) {
        if (line.startsWith("data: ")) {
          const dataStr = line.slice(6).trim()
          if (!dataStr) continue
          
          try {
            const data: SSEEvent = JSON.parse(dataStr)
            
            if (data.type === "chunk" && data.content) {
              fullText += data.content
              callbacks.onChunk(data.content)
            } else if (data.type === "done") {
              callbacks.onDone(fullText)
            } else if (data.type === "error") {
              callbacks.onError(data.message || "Unknown error")
            }
          } catch {
            // Ignore malformed JSON lines
          }
        }
      }
    }

    if (fullText.length > 0) {
      callbacks.onDone(fullText)
    }
  } catch (error) {
    if ((error as Error).name !== "AbortError") {
      callbacks.onError(error instanceof Error ? error.message : "Network error")
    }
  }

  return controller
}

export async function checkHealth(): Promise<boolean> {
  try {
    const response = await fetch(`${API_BASE_URL}/health`, {
      signal: AbortSignal.timeout(3000),
    })
    return response.ok
  } catch {
    return false
  }
}
