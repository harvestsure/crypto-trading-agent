"use client"

import { Bell, Search, Plus, User, LogOut } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { useState } from "react"
import { useRouter } from "next/navigation"
import { CreateAgentModal } from "@/components/modals/create-agent-modal"
import { useAppStore } from "@/lib/store"
import { useAuth } from "@/contexts/auth-context"
import { ThemeSwitcher } from "@/components/theme-switcher"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"

interface HeaderProps {
  title: string
  description?: string
  showCreateAgent?: boolean
}

export function Header({ title, description, showCreateAgent = false }: HeaderProps) {
  const [createModalOpen, setCreateModalOpen] = useState(false)
  const { fetchAgents } = useAppStore()
  const { user, logout } = useAuth()
  const router = useRouter()

  const handleAgentCreated = () => {
    fetchAgents()
  }

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
    <>
      <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-border bg-background/95 px-6 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="min-w-0 flex-1">
          <h1 className="text-xl font-semibold text-foreground truncate">{title}</h1>
          {description && <p className="text-sm text-muted-foreground truncate">{description}</p>}
        </div>

        <div className="flex items-center gap-3 ml-4">
          {showCreateAgent && (
            <Button onClick={() => setCreateModalOpen(true)} size="sm" className="gap-2">
              <Plus className="h-4 w-4" />
              Create Agent
            </Button>
          )}
          <div className="relative hidden lg:block">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input placeholder="Search..." className="w-64 bg-secondary pl-9 h-9" />
          </div>
          <Button variant="ghost" size="icon" className="relative h-9 w-9">
            <Bell className="h-5 w-5" />
            <span className="absolute -right-1 -top-1 flex h-4 w-4 items-center justify-center rounded-full bg-primary text-[10px] font-medium text-primary-foreground">
              3
            </span>
          </Button>

          <ThemeSwitcher />

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon" className="h-9 w-9 rounded-full">
                <Avatar className="h-8 w-8">
                  <AvatarFallback className="bg-primary text-primary-foreground text-xs">
                    {getUserInitials()}
                  </AvatarFallback>
                </Avatar>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-56">
              <DropdownMenuLabel>
                <div className="flex flex-col space-y-1">
                  <p className="text-sm font-medium">{user?.full_name || user?.username}</p>
                  <p className="text-xs text-muted-foreground">{user?.email}</p>
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
      </header>

      <CreateAgentModal open={createModalOpen} onOpenChange={setCreateModalOpen} onSuccess={handleAgentCreated} />
    </>
  )
}
