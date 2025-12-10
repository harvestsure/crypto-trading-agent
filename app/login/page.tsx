"use client"

import type React from "react"

import { useState, useEffect } from "react"
import { useAuth } from "@/contexts/auth-context"
import { useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import Link from "next/link"
import { Loader2, Bot, AlertCircle, Server } from "lucide-react"
import { Alert, AlertDescription } from "@/components/ui/alert"

export default function LoginPage() {
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState("")
  const { login, isAuthenticated, isLoading: authIsLoading } = useAuth()
  const router = useRouter()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    // Prevent double submission
    if (isLoading) {
      console.log("[LoginPage] Already submitting, ignoring duplicate")
      return
    }
    
    setIsLoading(true)
    setError("")

    try {
      await login({ username, password })
      // Navigation is handled by auth context
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed. Please check your credentials.")
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-linear-to-br from-background via-background to-muted/30 p-4">
      <Card className="w-full max-w-md shadow-lg border-border/50">
        <CardHeader className="space-y-1 text-center">
          <div className="flex justify-center mb-4">
            <div className="rounded-full bg-primary/10 p-3">
              <Bot className="h-8 w-8 text-primary" />
            </div>
          </div>
          <CardTitle className="text-2xl font-bold tracking-tight">Welcome Back</CardTitle>
          <CardDescription>Sign in to access your AI trading agents</CardDescription>
        
        </CardHeader>
        <form onSubmit={handleSubmit} className="space-y-6">
          <CardContent className="space-y-6">
            {error && (
              <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}
            <div className="space-y-2">
              <Label htmlFor="username">Username</Label>
              <Input
          id="username"
          type="text"
          placeholder="Enter your username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          required
          disabled={isLoading}
          autoComplete="username"
          className="h-11"
              />
            </div>
            <div className="space-y-2">
              <div className="flex items-center justify-between">
          <Label htmlFor="password">Password</Label>
          <Link
            href="/forgot-password"
            className="text-xs text-muted-foreground hover:text-primary transition-colors"
          >
            Forgot password?
          </Link>
              </div>
              <Input
          id="password"
          type="password"
          placeholder="Enter your password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          disabled={isLoading}
          autoComplete="current-password"
          className="h-11"
              />
            </div>
          </CardContent>
          <CardFooter className="flex flex-col gap-4 pt-2">
            <Button type="submit" className="w-full h-11" disabled={isLoading}>
              {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Sign In
            </Button>
            <div className="relative w-full">
              <div className="absolute inset-0 flex items-center">
          <span className="w-full border-t border-border" />
              </div>
              <div className="relative flex justify-center text-xs uppercase">
          <span className="bg-card px-2 text-muted-foreground">New to CryptoAgent?</span>
              </div>
            </div>
            <Link href="/register" className="w-full">
              <Button type="button" variant="outline" className="w-full h-11 bg-transparent">
          Create Account
              </Button>
            </Link>
          </CardFooter>
        </form>
      </Card>
    </div>
  )
}
