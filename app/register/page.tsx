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
import { Loader2, Bot, AlertCircle, CheckCircle2 } from "lucide-react"
import { Alert, AlertDescription } from "@/components/ui/alert"

export default function RegisterPage() {
  const [formData, setFormData] = useState({
    username: "",
    email: "",
    password: "",
    confirmPassword: "",
    full_name: "",
  })
  const [isLoading, setIsLoading] = useState(false)
  const [errors, setErrors] = useState<string[]>([])
  const { register, isAuthenticated } = useAuth()
  const router = useRouter()

  useEffect(() => {
    if (isAuthenticated) {
      router.push("/")
    }
  }, [isAuthenticated, router])

  const validateForm = (): boolean => {
    const newErrors: string[] = []

    if (formData.username.length < 3) {
      newErrors.push("Username must be at least 3 characters")
    }

    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email)) {
      newErrors.push("Please enter a valid email address")
    }

    if (formData.password.length < 6) {
      newErrors.push("Password must be at least 6 characters")
    }

    if (formData.password !== formData.confirmPassword) {
      newErrors.push("Passwords do not match")
    }

    setErrors(newErrors)
    return newErrors.length === 0
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    if (!validateForm()) {
      return
    }

    setIsLoading(true)
    setErrors([])

    try {
      await register({
        username: formData.username,
        email: formData.email,
        password: formData.password,
        full_name: formData.full_name || undefined,
      })
    } catch (err) {
      setErrors([err instanceof Error ? err.message : "Registration failed. Please try again."])
    } finally {
      setIsLoading(false)
    }
  }

  const handleChange = (field: string, value: string) => {
    setFormData((prev) => ({ ...prev, [field]: value }))
    setErrors([]) // Clear errors when user types
  }

  const passwordStrength = (password: string): { strength: string; color: string } => {
    if (password.length === 0) return { strength: "", color: "" }
    if (password.length < 6) return { strength: "Weak", color: "text-red-500" }
    if (password.length < 10) return { strength: "Medium", color: "text-yellow-500" }
    return { strength: "Strong", color: "text-green-500" }
  }

  const strength = passwordStrength(formData.password)

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-background via-background to-muted/30 p-4">
      <Card className="w-full max-w-md shadow-lg border-border/50">
        <CardHeader className="space-y-1 text-center">
          <div className="flex justify-center mb-4">
            <div className="rounded-full bg-primary/10 p-3">
              <Bot className="h-8 w-8 text-primary" />
            </div>
          </div>
          <CardTitle className="text-2xl font-bold tracking-tight">Create Your Account</CardTitle>
          <CardDescription>Start your journey with AI-powered crypto trading</CardDescription>
        </CardHeader>
        <form onSubmit={handleSubmit}>
          <CardContent className="space-y-4">
            {errors.length > 0 && (
              <Alert variant="destructive">
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>
                  <ul className="list-disc list-inside space-y-1">
                    {errors.map((error, i) => (
                      <li key={i}>{error}</li>
                    ))}
                  </ul>
                </AlertDescription>
              </Alert>
            )}
            <div className="space-y-2">
              <Label htmlFor="username">Username *</Label>
              <Input
                id="username"
                type="text"
                placeholder="Choose a username"
                value={formData.username}
                onChange={(e) => handleChange("username", e.target.value)}
                required
                minLength={3}
                disabled={isLoading}
                autoComplete="username"
                className="h-11"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="email">Email *</Label>
              <Input
                id="email"
                type="email"
                placeholder="your@email.com"
                value={formData.email}
                onChange={(e) => handleChange("email", e.target.value)}
                required
                disabled={isLoading}
                autoComplete="email"
                className="h-11"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="full_name">Full Name (Optional)</Label>
              <Input
                id="full_name"
                type="text"
                placeholder="John Doe"
                value={formData.full_name}
                onChange={(e) => handleChange("full_name", e.target.value)}
                disabled={isLoading}
                autoComplete="name"
                className="h-11"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Password *</Label>
              <Input
                id="password"
                type="password"
                placeholder="Create a strong password"
                value={formData.password}
                onChange={(e) => handleChange("password", e.target.value)}
                required
                minLength={6}
                disabled={isLoading}
                autoComplete="new-password"
                className="h-11"
              />
              {formData.password && (
                <p className={`text-xs ${strength.color}`}>
                  Password strength: <span className="font-medium">{strength.strength}</span>
                </p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="confirmPassword">Confirm Password *</Label>
              <Input
                id="confirmPassword"
                type="password"
                placeholder="Confirm your password"
                value={formData.confirmPassword}
                onChange={(e) => handleChange("confirmPassword", e.target.value)}
                required
                minLength={6}
                disabled={isLoading}
                autoComplete="new-password"
                className="h-11"
              />
              {formData.confirmPassword && formData.password === formData.confirmPassword && (
                <div className="flex items-center gap-1 text-xs text-green-500">
                  <CheckCircle2 className="h-3 w-3" />
                  <span>Passwords match</span>
                </div>
              )}
            </div>
          </CardContent>
          <CardFooter className="flex flex-col gap-4">
            <Button type="submit" className="w-full h-11 mt-6" disabled={isLoading}>
              {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Create Account
            </Button>
            <div className="relative w-full">
              <div className="absolute inset-0 flex items-center">
                <span className="w-full border-t border-border" />
              </div>
              <div className="relative flex justify-center text-xs uppercase">
                <span className="bg-card px-2 text-muted-foreground">Already have an account?</span>
              </div>
            </div>
            <Link href="/login" className="w-full">
              <Button type="button" variant="outline" className="w-full h-11 bg-transparent">
                Sign In
              </Button>
            </Link>
          </CardFooter>
        </form>
      </Card>
    </div>
  )
}
