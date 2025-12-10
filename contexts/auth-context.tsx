"use client"

import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from "react"
import { authAPI, type User, type LoginData, type RegisterData } from "@/lib/auth"
import { useRouter } from "next/navigation"
import { toast } from "@/hooks/use-toast"

interface AuthContextType {
  user: User | null
  isLoading: boolean
  isAuthenticated: boolean
  login: (data: LoginData) => Promise<void>
  register: (data: RegisterData) => Promise<void>
  logout: () => Promise<void>
  refreshUser: () => Promise<void>
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const router = useRouter()

  useEffect(() => {
    // Check if user is authenticated on mount
    const initAuth = async () => {
      try {
        const storedUser = authAPI.getStoredUser()
        const hasToken = authAPI.isAuthenticated()
        
        console.log("[Auth] Initializing - hasToken:", hasToken, "storedUser:", storedUser?.username)
        
        if (storedUser && hasToken) {
          // Set user immediately from cookie
          // This allows the ProtectedRoute to render the page
          setUser(storedUser)
          console.log("[Auth] User loaded from cookie:", storedUser.username)
          
          // Try to verify token in the background, but don't block
          try {
            const isValid = await authAPI.verifyToken()
            console.log("[Auth] Token verification result:", isValid)
            if (!isValid) {
              authAPI.clearToken()
              setUser(null)
              console.log("[Auth] Token verification failed, clearing")
            }
          } catch (error) {
            console.error("[Auth] Token verification error:", error)
            // Don't clear token on network error, user might be offline
            // Just log it and continue
          }
        } else {
          console.log("[Auth] No stored user or token found")
          setUser(null)
        }
      } catch (error) {
        console.error("[Auth] Initialization error:", error)
        setUser(null)
      } finally {
        setIsLoading(false)
      }
    }

    initAuth()
  }, [])

  const login = useCallback(async (data: LoginData) => {
    try {
      console.log("[Auth] Starting login for user:", data.username)
      const response = await authAPI.login(data)
      console.log("[Auth] Login successful, setting user:", response.user.username)
      setUser(response.user)
      
      toast({
        title: "Welcome back!",
        description: `Logged in as ${response.user.username}`,
      })
      
      // Navigate to home page
      console.log("[Auth] Navigating to home")
      router.push("/")
    } catch (error) {
      console.error("[Auth] Login error:", error)
      toast({
        title: "Login failed",
        description: error instanceof Error ? error.message : "Please check your credentials",
        variant: "destructive",
      })
      throw error
    }
  }, [router, toast])

  const register = useCallback(async (data: RegisterData) => {
    try {
      console.log("[Auth] Starting registration for user:", data.username)
      const response = await authAPI.register(data)
      console.log("[Auth] Registration successful, setting user:", response.user.username)
      setUser(response.user)
      
      toast({
        title: "Account created!",
        description: `Welcome ${response.user.username}`,
      })
      
      // Navigate to home page
      console.log("[Auth] Navigating to home")
      router.push("/")
    } catch (error) {
      console.error("[Auth] Registration error:", error)
      toast({
        title: "Registration failed",
        description: error instanceof Error ? error.message : "Please try again",
        variant: "destructive",
      })
      throw error
    }
  }, [router, toast])

  const logout = useCallback(async () => {
    try {
      await authAPI.logout()
      setUser(null)
      toast({
        title: "Logged out",
        description: "You have been successfully logged out",
      })
      router.push("/login")
    } catch (error) {
      console.error("Logout error:", error)
    }
  }, [router])

  const refreshUser = useCallback(async () => {
    try {
      const currentUser = await authAPI.getCurrentUser()
      setUser(currentUser)
    } catch (error) {
      console.error("Failed to refresh user:", error)
      setUser(null)
    }
  }, [])

  useEffect(() => {
    console.log("[AuthProvider] Context updated - user:", user?.username, "isAuthenticated:", !!user, "isLoading:", isLoading)
  }, [user, isLoading])

  return (
    <AuthContext.Provider
      value={{
        user,
        isLoading,
        isAuthenticated: !!user,
        login,
        register,
        logout,
        refreshUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider")
  }
  return context
}
