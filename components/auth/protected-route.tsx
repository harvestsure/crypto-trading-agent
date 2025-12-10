"use client"

import type React from "react"

import { useEffect, useState } from "react"
import { useAuth } from "@/contexts/auth-context"
import { useRouter } from "next/navigation"
import { Loader2 } from "lucide-react"

interface ProtectedRouteProps {
  children: React.ReactNode
  redirectTo?: string
}

export function ProtectedRoute({ children, redirectTo = "/login" }: ProtectedRouteProps) {
  const { isAuthenticated, isLoading, user } = useAuth()
  const router = useRouter()
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    console.log("[ProtectedRoute] Mounting component")
    setMounted(true)
  }, [])

  useEffect(() => {
    if (!mounted) return
    
    console.log("[ProtectedRoute] Auth state check - isLoading:", isLoading, "isAuthenticated:", isAuthenticated, "user:", user?.username, "mounted:", mounted)
    
    if (!isLoading && !isAuthenticated) {
      console.log("[ProtectedRoute] Not authenticated, redirecting to:", redirectTo)
      router.push(redirectTo)
    } else if (!isLoading && isAuthenticated) {
      console.log("[ProtectedRoute] Authenticated, rendering children for user:", user?.username)
    }
  }, [isAuthenticated, isLoading, router, redirectTo, user, mounted])

  if (!mounted || isLoading) {
    console.log("[ProtectedRoute] Rendering loading state - mounted:", mounted, "isLoading:", isLoading)
    return (
      <div className="flex items-center justify-center min-h-screen bg-background">
        <div className="text-center space-y-4">
          <Loader2 className="h-8 w-8 animate-spin mx-auto text-primary" />
          <p className="text-sm text-muted-foreground">Loading...</p>
        </div>
      </div>
    )
  }

  if (!isAuthenticated) {
    console.log("[ProtectedRoute] Not authenticated, returning null")
    return null
  }

  console.log("[ProtectedRoute] Rendering children")
  return <>{children}</>
}
