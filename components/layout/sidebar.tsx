"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { cn } from "@/lib/utils"
import { Bot, Building2, LayoutDashboard, Brain, Settings, Activity, Wifi, Server } from "lucide-react"
import { useWebSocket } from "@/hooks/use-websocket"
import { useEffect, useState } from "react"

const navigation = [
  { name: "Dashboard", href: "/", icon: LayoutDashboard },
  { name: "AI Models", href: "/models", icon: Brain },
  { name: "Exchanges", href: "/exchanges", icon: Building2 },
  { name: "Agents", href: "/agents", icon: Bot },
  { name: "Activity", href: "/activity", icon: Activity },
  { name: "Settings", href: "/settings", icon: Settings },
]

export function Sidebar() {
  const pathname = usePathname()
  const { status: wsStatus } = useWebSocket()
  const [backendStatus, setBackendStatus] = useState<"connected" | "disconnected" | "checking">("checking")

  useEffect(() => {
    const checkBackend = async () => {
      try {
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"
        const response = await fetch(`${apiUrl}/health`, {
          method: "GET",
          signal: AbortSignal.timeout(3000),
        })
        if (response.ok) {
          setBackendStatus("connected")
        } else {
          setBackendStatus("disconnected")
        }
      } catch {
        setBackendStatus("disconnected")
      }
    }

    checkBackend()
    const interval = setInterval(checkBackend, 10000) // Check every 10 seconds
    return () => clearInterval(interval)
  }, [])

  return (
    <aside className="fixed left-0 top-0 z-40 h-screen w-64 border-r border-border bg-sidebar">
      <div className="flex h-full flex-col">
        <div className="flex h-16 items-center gap-2 border-b border-border px-6">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary">
            <Bot className="h-5 w-5 text-primary-foreground" />
          </div>
          <span className="text-lg font-semibold text-foreground">CryptoAgent</span>
        </div>

        <nav className="flex-1 space-y-1 px-3 py-4">
          {navigation.map((item) => {
            const isActive = pathname === item.href
            return (
              <Link
                key={item.name}
                href={item.href}
                className={cn(
                  "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                  isActive
                    ? "bg-sidebar-accent text-primary"
                    : "text-muted-foreground hover:bg-sidebar-accent hover:text-foreground",
                )}
              >
                <item.icon className="h-5 w-5" />
                {item.name}
              </Link>
            )
          })}
        </nav>

        <div className="border-t border-border p-4">
          <div className="rounded-lg bg-secondary/50 p-3 space-y-3">
            <p className="text-xs font-medium text-foreground">System Status</p>

            {/* Backend Status */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Server className="h-4 w-4 text-muted-foreground" />
                <span className="text-xs text-muted-foreground">Backend</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className={cn("relative flex h-2 w-2")}>
                  {backendStatus === "connected" && (
                    <>
                      <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-success opacity-75"></span>
                      <span className="relative inline-flex h-2 w-2 rounded-full bg-success"></span>
                    </>
                  )}
                  {backendStatus === "disconnected" && (
                    <span className="relative inline-flex h-2 w-2 rounded-full bg-destructive"></span>
                  )}
                  {backendStatus === "checking" && (
                    <span className="relative inline-flex h-2 w-2 rounded-full bg-warning animate-pulse"></span>
                  )}
                </span>
                <span
                  className={cn(
                    "text-xs",
                    backendStatus === "connected"
                      ? "text-success"
                      : backendStatus === "disconnected"
                        ? "text-destructive"
                        : "text-warning",
                  )}
                >
                  {backendStatus === "connected"
                    ? "Connected"
                    : backendStatus === "disconnected"
                      ? "Disconnected"
                      : "Checking..."}
                </span>
              </div>
            </div>

            {/* WSS Feed Status */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Wifi className="h-4 w-4 text-muted-foreground" />
                <span className="text-xs text-muted-foreground">WSS Feed</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="relative flex h-2 w-2">
                  {wsStatus === "connected" ? (
                    <>
                      <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-success opacity-75"></span>
                      <span className="relative inline-flex h-2 w-2 rounded-full bg-success"></span>
                    </>
                  ) : wsStatus === "error" ? (
                    <span className="relative inline-flex h-2 w-2 rounded-full bg-destructive"></span>
                  ) : (
                    <span className="relative inline-flex h-2 w-2 rounded-full bg-muted-foreground"></span>
                  )}
                </span>
                <span
                  className={cn(
                    "text-xs",
                    wsStatus === "connected"
                      ? "text-success"
                      : wsStatus === "error"
                        ? "text-destructive"
                        : "text-muted-foreground",
                  )}
                >
                  {wsStatus === "connected" ? "Active" : wsStatus === "error" ? "Error" : "Inactive"}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </aside>
  )
}
