"use client"

import type React from "react"
import { Sidebar } from "@/components/layout/sidebar"
import { Header } from "@/components/layout/header"
import { useSidebar } from "@/contexts/sidebar-context"
import { ProtectedRoute } from "@/components/auth/protected-route"

export default function AuthenticatedLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  const { isOpen } = useSidebar()

  return (
    <ProtectedRoute>
      <div className="flex h-screen overflow-hidden">
        <Sidebar />
        <main className={`flex-1 transition-all duration-300 ease-in-out flex flex-col min-h-0 overflow-hidden ${isOpen ? "pl-64" : "pl-16"}`}>
          <Header />
          <div className="flex-1 min-h-0 overflow-hidden">
            {children}
          </div>
        </main>
      </div>
    </ProtectedRoute>
  )
}
