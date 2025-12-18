"use client"

import Link from "next/link"
import { usePathname, useRouter } from "next/navigation"
import { cn } from "@/lib/utils"
import { Bot, Building2, LayoutDashboard, Brain, Settings, Activity, Wifi, Server, User, LogOut } from "lucide-react"
import { useWebSocket } from "@/hooks/use-websocket"
import { useAuth } from "@/contexts/auth-context"
import { useSidebar } from "@/contexts/sidebar-context"
import { useEffect, useState } from "react"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"

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
  const router = useRouter()
  const { status: wsStatus } = useWebSocket()
  const { user, logout } = useAuth()
  const { isOpen, toggle } = useSidebar()
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
    const interval = setInterval(checkBackend, 10000)
    return () => clearInterval(interval)
  }, [])

  const getUserInitials = () => {
    if (!user) return "U"
    if (user.full_name) {
      const names = user.full_name.split(" ")
      return names
        .map((n) => n[0])
        .join("")
        .toUpperCase()
        .slice(0, 2)
    }
    return user.username.slice(0, 2).toUpperCase()
  }

  return (
    <aside
      className={cn(
        "fixed left-0 top-0 z-40 h-full border-r border-border bg-sidebar transition-all duration-300 ease-in-out",
        isOpen ? "w-64" : "w-16",
      )}
    >
      <div className="flex h-full flex-col">
        <div className="flex h-16 items-center justify-between border-b border-border px-4">
          {isOpen && (
            <div className="flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary">
                <Bot className="h-5 w-5 text-primary-foreground" />
              </div>
              <span className="text-lg font-semibold text-foreground">CryptoAgent</span>
            </div>
          )}
          {!isOpen && (
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary">
              <Bot className="h-5 w-5 text-primary-foreground" />
            </div>
          )}
          {/* toggle moved to footer to avoid compressing logo when collapsed */}
        </div>

        <nav className="flex-1 space-y-1 px-2 py-4">
          {navigation.map((item) => {
            const isActive = pathname === item.href
            return (
              <Link
                key={item.name}
                href={item.href}
                className={cn(
                  "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors justify-center",
                  isOpen && "justify-start",
                  isActive
                    ? "bg-sidebar-accent text-primary"
                    : "text-muted-foreground hover:bg-sidebar-accent hover:text-foreground",
                )}
                title={!isOpen ? item.name : undefined}
              >
                  <item.icon className="h-5 w-5 shrink-0" />
                  <span
                    className={cn(
                      "ml-2 truncate whitespace-nowrap",
                      !isOpen && "sr-only",
                    )}
                  >
                    {item.name}
                  </span>
              </Link>
            )
          })}
        </nav>

        {user && (
          <div className="border-t border-border p-3">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button 
                  variant="ghost" 
                  className={cn(
                    "h-auto hover:bg-sidebar-accent",
                    isOpen ? "w-full justify-start px-3 py-2" : "w-full px-2 py-2 justify-center"
                  )}
                >
                  <div className={cn("flex items-center gap-3", isOpen && "w-full")}>
                    <Avatar className="h-8 w-8 shrink-0">
                      <AvatarFallback className="bg-primary text-primary-foreground text-xs">
                        {getUserInitials()}
                      </AvatarFallback>
                    </Avatar>
                    {isOpen && (
                      <div className="flex-1 min-w-0 text-left">
                        <p className="text-sm font-medium text-foreground truncate">{user.username}</p>
                        <p className="text-xs text-muted-foreground truncate">{user.email}</p>
                      </div>
                    )}
                  </div>
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent side="top" align="start" className="w-56 mb-2">
                <DropdownMenuLabel>
                  <div className="flex flex-col space-y-1">
                    <p className="text-sm font-medium">{user.full_name || user.username}</p>
                    <p className="text-xs text-muted-foreground">{user.email}</p>
                  </div>
                </DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={() => router.push("/profile")} className="cursor-pointer">
                  <User className="mr-2 h-4 w-4" />
                  View Profile
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={logout} className="cursor-pointer text-destructive focus:text-destructive">
                  <LogOut className="mr-2 h-4 w-4" />
                  Log out
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        )}

        <div className="border-t border-border p-3">
          <div className={cn("rounded-lg bg-secondary/50 p-2 space-y-2", isOpen ? "p-3 space-y-3" : "p-2")}>
            {isOpen && <p className="text-xs font-medium text-foreground">System Status</p>}

            <div className={cn("flex items-center justify-between", !isOpen && "flex-col gap-2")}>
              <div className="flex items-center gap-2">
                <Server className="h-4 w-4 text-muted-foreground shrink-0" />
                <span
                  className={cn(
                    "text-xs text-muted-foreground truncate whitespace-nowrap",
                    !isOpen && "sr-only",
                  )}
                >
                  Backend
                </span>
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
                    "text-xs truncate whitespace-nowrap",
                    backendStatus === "connected"
                      ? "text-success"
                      : backendStatus === "disconnected"
                        ? "text-destructive"
                        : "text-warning",
                    !isOpen && "sr-only",
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

            <div className={cn("flex items-center justify-between", !isOpen && "flex-col gap-2")}> 
              <div className="flex items-center gap-2">
                <Wifi className="h-4 w-4 text-muted-foreground shrink-0" />
                <span className={cn("text-xs text-muted-foreground truncate whitespace-nowrap", !isOpen && "sr-only")}>
                  WSS Feed
                </span>
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
                    "text-xs truncate whitespace-nowrap",
                    wsStatus === "connected"
                      ? "text-success"
                      : wsStatus === "error"
                        ? "text-destructive"
                        : "text-muted-foreground",
                    !isOpen && "sr-only",
                  )}
                >
                  {wsStatus === "connected" ? "Active" : wsStatus === "error" ? "Error" : "Inactive"}
                </span>
              </div>
            </div>
          </div>
        </div>
        {/* toggle moved to header; footer toggle removed */}
      </div>
    </aside>
  )
}
