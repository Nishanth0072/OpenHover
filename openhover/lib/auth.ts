import { API_BASE_URL } from "./constants"

export interface AuthResponse {
  success: boolean
  message?: string
  data?: any
}

export async function sendRegisterOtp(email: string, password: string): Promise<AuthResponse> {
  try {
    const res = await fetch(`${API_BASE_URL}/auth/register/send-otp`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    })
    const data = await res.json()
    if (!res.ok) {
      return { success: false, message: data.detail || "Failed to send OTP" }
    }
    return { success: true, data }
  } catch (err: any) {
    return { success: false, message: err.message || "Network error" }
  }
}

export async function verifyRegister(email: string, otp: string, registrationToken: string): Promise<AuthResponse> {
  try {
    const res = await fetch(`${API_BASE_URL}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, otp, registration_token: registrationToken }),
    })
    const data = await res.json()
    if (!res.ok) {
      return { success: false, message: data.detail || "Failed to verify registration" }
    }
    return { success: true, data }
  } catch (err: any) {
    return { success: false, message: err.message || "Network error" }
  }
}

export async function initiateLogin(email: string, password: string): Promise<AuthResponse> {
  try {
    const res = await fetch(`${API_BASE_URL}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    })
    const data = await res.json()
    if (!res.ok) {
      return { success: false, message: data.detail || "Login failed" }
    }
    return { success: true, data }
  } catch (err: any) {
    return { success: false, message: err.message || "Network error" }
  }
}

export async function verifyLoginOtp(mfaToken: string, otp: string): Promise<AuthResponse> {
  try {
    const res = await fetch(`${API_BASE_URL}/auth/login/verify`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mfa_token: mfaToken, otp }),
    })
    const data = await res.json()
    if (!res.ok) {
      return { success: false, message: data.detail || "OTP verification failed" }
    }
    return { success: true, data }
  } catch (err: any) {
    return { success: false, message: err.message || "Network error" }
  }
}
