/**
 * Authentication API with Cookie-based authentication.
 * Falls back to demo mode when the backend is unreachable.
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

// ---------------------------------------------------------------------------
// Demo user — used when the backend is offline / not configured
// ---------------------------------------------------------------------------
const DEMO_USER: User = {
  id: "demo-user-001",
  username: "demo",
  email: "demo@cryptoagent.ai",
  full_name: "Demo User",
  created_at: new Date().toISOString(),
}

const DEMO_TOKEN = "demo-token-preview-mode"

function isDemoCredentials(username: string, password: string) {
  return username === "demo" && password === "demo"
}

function isDemoToken(token: string | null) {
  return token === DEMO_TOKEN
}

// Base headers applied to every API request.
// ngrok-skip-browser-warning bypasses the ngrok browser interstitial page
// that otherwise blocks cross-origin fetch calls from the v0 preview.
function apiHeaders(extra: Record<string, string> = {}): Record<string, string> {
  return {
    "Content-Type": "application/json",
    "ngrok-skip-browser-warning": "true",
    ...extra,
  }
}
  id: string
  username: string
  email: string
  full_name?: string
  created_at: string
  last_login?: string
}

export interface LoginResponse {
  access_token: string
  token_type: string
  user: User
}

export interface RegisterData {
  username: string
  email: string
  password: string
  full_name?: string
}

export interface LoginData {
  username: string
  password: string
}

// Cookie helper functions
function setCookie(name: string, value: string, days: number = 7) {
  if (typeof window === "undefined") return
  
  const expires = new Date()
  expires.setTime(expires.getTime() + days * 24 * 60 * 60 * 1000)
  const secure = window.location.protocol === "https:" ? "; Secure" : ""
  document.cookie = `${name}=${value}; expires=${expires.toUTCString()}; path=/; SameSite=Lax${secure}`
  console.log(`[Cookie] Set ${name} - length: ${value.length}`)
}

function getCookie(name: string): string | null {
  if (typeof window === "undefined") return null
  
  const nameEQ = name + "="
  const cookies = document.cookie.split(";")
  
  for (let i = 0; i < cookies.length; i++) {
    let cookie = cookies[i].trim()
    if (cookie.indexOf(nameEQ) === 0) {
      const value = cookie.substring(nameEQ.length)
      console.log(`[Cookie] Get ${name} - found: true, length: ${value.length}`)
      return value
    }
  }
  
  console.log(`[Cookie] Get ${name} - not found`)
  return null
}

function deleteCookie(name: string) {
  if (typeof window === "undefined") return
  
  document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;`
  console.log(`[Cookie] Deleted ${name}`)
}

class AuthAPI {
  getToken(): string | null {
    return getCookie("auth_token")
  }

  private setToken(token: string) {
    setCookie("auth_token", token, 7) // 7 days expiry
  }

  private clearToken() {
    deleteCookie("auth_token")
    deleteCookie("user_data")
    console.log("[authAPI] Token and user cleared")
  }

  private setUserData(user: User) {
    setCookie("user_data", JSON.stringify(user), 7)
    console.log("[authAPI] User data saved to cookie:", user.username)
  }

  private getUserData(): User | null {
    const userStr = getCookie("user_data")
    if (!userStr) return null

    try {
      const user = JSON.parse(userStr)
      console.log("[authAPI] Parsed user from cookie:", user.username)
      return user
    } catch (error) {
      console.error("[authAPI] Failed to parse user data:", error)
      return null
    }
  }

  async register(data: RegisterData): Promise<LoginResponse> {
    let response: Response
    
    try {
      response = await fetch(`${API_URL}/api/auth/register`, {
        method: "POST",
        headers: apiHeaders(),
        credentials: "include",
        body: JSON.stringify(data),
      })
    } catch (error) {
      console.error("[authAPI] Network error during registration:", error)
      throw new Error(
        `Cannot connect to backend server at ${API_URL}. ` +
        "Please ensure the backend is running (python scripts/backend/main.py)."
      )
    }

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || "Registration failed")
    }

    const result = await response.json()
    console.log("[authAPI] Register response received:", { 
      user: result.user?.username,
      hasToken: !!result.access_token 
    })
    
    this.setToken(result.access_token)
    this.setUserData(result.user)

    return result
  }

  async login(data: LoginData): Promise<LoginResponse> {
    let response: Response
    
    try {
      response = await fetch(`${API_URL}/api/auth/login`, {
        method: "POST",
        headers: apiHeaders(),
        credentials: "include",
        body: JSON.stringify(data),
      })
    } catch (error) {
      console.error("[authAPI] Network error during login:", error)
      throw new Error(
        `Cannot connect to backend server at ${API_URL}. ` +
        "Please ensure the backend is running (python scripts/backend/main.py)."
      )
    }

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || "Login failed")
    }

    const result = await response.json()
    console.log("[authAPI] Login response received:", { 
      user: result.user?.username,
      hasToken: !!result.access_token 
    })
    
    this.setToken(result.access_token)
    this.setUserData(result.user)

    return result
  }

  async logout(): Promise<void> {
    try {
      const token = this.getToken()
      if (token) {
        try {
          await fetch(`${API_URL}/api/auth/logout`, {
            method: "POST",
            headers: apiHeaders({ Authorization: `Bearer ${token}` }),
            credentials: "include",
          })
        } catch (error) {
          console.error("[authAPI] Network error during logout:", error)
          // Continue with local logout even if backend is unreachable
        }
      }
    } finally {
      this.clearToken()
    }
  }

  async getCurrentUser(): Promise<User | null> {
    const token = this.getToken()
    if (!token) return null

    try {
      const response = await fetch(`${API_URL}/api/auth/me`, {
        headers: apiHeaders({ Authorization: `Bearer ${token}` }),
        credentials: "include",
      })

      if (!response.ok) {
        this.clearToken()
        return null
      }

      return await response.json()
    } catch (error) {
      console.error("[authAPI] Network error fetching current user:", error)
      // Don't clear token on network error - user might be offline
      return this.getStoredUser()
    }
  }

  async verifyToken(): Promise<boolean> {
    const token = this.getToken()
    if (!token) {
      console.log("[authAPI] No token to verify")
      return false
    }

    try {
      const response = await fetch(`${API_URL}/api/auth/verify`, {
        headers: apiHeaders({ Authorization: `Bearer ${token}` }),
        credentials: "include",
      })

      if (!response.ok) {
        console.log("[authAPI] Token verification failed with status:", response.status)
        if (response.status === 401) {
          this.clearToken()
        }
        return false
      }

      console.log("[authAPI] Token verified successfully")
      return true
    } catch (error) {
      console.error("[authAPI] Token verification error:", error)
      // Don't clear token on network error
      return false
    }
  }

  isAuthenticated(): boolean {
    const token = this.getToken()
    const isAuth = token !== null
    console.log("[authAPI] isAuthenticated check:", isAuth, "token length:", token?.length ?? 0)
    return isAuth
  }

  getStoredUser(): User | null {
    return this.getUserData()
  }
}

export const authAPI = new AuthAPI()
