import React, { useState } from "react"
import { initiateLogin, verifyLoginOtp, sendRegisterOtp, verifyRegister } from "../lib/auth"
import "./AuthScreen.css"
import iconBase64 from "data-base64:~assets/icon.png"

interface AuthScreenProps {
  onSuccess: (accessToken: string) => void
}

const AuthScreen: React.FC<AuthScreenProps> = ({ onSuccess }) => {
  const [isLogin, setIsLogin] = useState(true)
  const [step, setStep] = useState<"credentials" | "otp">("credentials")
  
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [otp, setOtp] = useState("")
  
  const [tokenData, setTokenData] = useState<string>("") // stores mfa_token or registration_token
  
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleCredentialsSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setLoading(true)
    
    try {
      if (isLogin) {
        const res = await initiateLogin(email, password)
        if (res.success) {
          setTokenData(res.data.mfa_token)
          setStep("otp")
        } else {
          setError(res.message || "Login failed")
        }
      } else {
        const res = await sendRegisterOtp(email, password)
        if (res.success) {
          setTokenData(res.data.registration_token)
          setStep("otp")
        } else {
          setError(res.message || "Signup failed")
        }
      }
    } catch (err: any) {
      setError(err.message || "An unexpected error occurred")
    } finally {
      setLoading(false)
    }
  }

  const handleOtpSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setLoading(true)
    
    try {
      if (isLogin) {
        const res = await verifyLoginOtp(tokenData, otp)
        if (res.success) {
          onSuccess(res.data.access_token)
        } else {
          setError(res.message || "Invalid OTP")
        }
      } else {
        const res = await verifyRegister(email, otp, tokenData)
        if (res.success) {
          onSuccess(res.data.access_token)
        } else {
          setError(res.message || "Invalid OTP")
        }
      }
    } catch (err: any) {
      setError(err.message || "An unexpected error occurred")
    } finally {
      setLoading(false)
    }
  }

  const toggleMode = () => {
    setIsLogin(!isLogin)
    setStep("credentials")
    setError(null)
    setOtp("")
    setPassword("")
  }

  return (
    <div className="hm-auth-container">
      <div className="hm-auth-card">
        <div className="hm-auth-header">
          <div className="hm-auth-logo">
            <img src={iconBase64} alt="OpenHover Logo" width="48" height="48" style={{ borderRadius: "12px", objectFit: "cover", display: "block" }} />
          </div>
          <h1 className="hm-auth-title">{isLogin ? "Welcome Back" : "Create Account"}</h1>
          <p className="hm-auth-subtitle">
            {step === "credentials" 
              ? (isLogin ? "Log in to use OpenHover AI" : "Sign up for OpenHover AI") 
              : "Check your email for the OTP code"}
          </p>
        </div>

        {error && (
          <div className="hm-auth-error">
            <span className="hm-auth-error-icon">⚠</span> {error}
          </div>
        )}

        {step === "credentials" ? (
          <form onSubmit={handleCredentialsSubmit} className="hm-auth-form">
            <div className="hm-input-group">
              <label>Email Address</label>
              <input 
                type="email" 
                value={email} 
                onChange={e => setEmail(e.target.value)} 
                placeholder="you@example.com"
                required 
                disabled={loading}
              />
            </div>
            <div className="hm-input-group">
              <label>Password</label>
              <input 
                type="password" 
                value={password} 
                onChange={e => setPassword(e.target.value)} 
                placeholder="••••••••"
                required 
                disabled={loading}
              />
            </div>
            <button type="submit" className="hm-auth-btn" disabled={loading}>
              {loading ? "Please wait..." : (isLogin ? "Log In" : "Sign Up")}
            </button>
            <div className="hm-auth-footer">
              <span className="hm-auth-switch-text">
                {isLogin ? "Don't have an account?" : "Already have an account?"}
              </span>
              <button type="button" onClick={toggleMode} className="hm-auth-switch-btn" disabled={loading}>
                {isLogin ? "Sign up" : "Log in"}
              </button>
            </div>
          </form>
        ) : (
          <form onSubmit={handleOtpSubmit} className="hm-auth-form">
            <div className="hm-input-group">
              <label>Enter OTP Code</label>
              <input 
                type="text" 
                value={otp} 
                onChange={e => setOtp(e.target.value)} 
                placeholder="123456"
                required 
                disabled={loading}
                autoFocus
                maxLength={6}
              />
            </div>
            <button type="submit" className="hm-auth-btn" disabled={loading || otp.length < 6}>
              {loading ? "Verifying..." : "Verify & Continue"}
            </button>
            <div className="hm-auth-footer">
              <button type="button" onClick={() => setStep("credentials")} className="hm-auth-switch-btn" disabled={loading}>
                ← Back
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  )
}

export default AuthScreen
