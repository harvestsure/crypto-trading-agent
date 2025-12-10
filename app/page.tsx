"use client"

import { useEffect } from "react"
import { useAppStore } from "@/lib/store"
import { useAuth } from "@/contexts/auth-context"
import { ProtectedRoute } from "@/components/auth/protected-route"
import { Sidebar } from "@/components/layout/sidebar"
import { Header } from "@/components/layout/header"
import { StatsCard } from "@/components/dashboard/stats-card"
import { AgentCard } from "@/components/dashboard/agent-card"
import { Bot, Brain, Building2, TrendingUp } from "lucide-react"
import { Card } from "@/components/ui/card"
import { Toaster } from "sonner"

function DashboardContent() {
  const { models, exchanges, agents, updateAgent, deleteAgent, fetchModels, fetchExchanges, fetchAgents } =
    useAppStore()
  const { user } = useAuth()

  useEffect(() => {
    console.log("[Dashboard] Mounted, user:", user?.username)
    fetchModels()
    fetchExchanges()
    fetchAgents()
  }, [fetchModels, fetchExchanges, fetchAgents, user])

  const runningAgents = agents.filter((a) => a.status === "running").length
  const totalPnl = agents.reduce((acc, a) => acc + (a.performance?.pnl ?? 0), 0)

  const handleToggleAgent = async (agentId: string) => {
    const agent = agents.find((a) => a.id === agentId)
    if (agent) {
      const newStatus = agent.status === "running" ? "paused" : "running"
      const result = await updateAgent(agentId, { status: newStatus })
      if (result.success) {
        fetchAgents()
      }
    }
  }

  const handleDeleteAgent = async (agentId: string) => {
    const result = await deleteAgent(agentId)
    if (result.success) {
      fetchAgents()
    }
  }

  return (
    <div className="flex min-h-screen bg-background">
      <Sidebar />
      <main className="flex-1 pl-64">
        <Header
          title={`Welcome, ${user?.username || "Trader"}`}
          description="Overview of your trading agents and performance"
          showCreateAgent={false}
        />

        <div className="p-6 space-y-6 max-w-[1800px]">
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            <StatsCard title="AI Models" value={models.length} icon={Brain} />
            <StatsCard title="Exchanges" value={exchanges.length} icon={Building2} />
            <StatsCard title="Active Agents" value={runningAgents} change={`of ${agents.length} total`} icon={Bot} />
            <StatsCard
              title="Total PnL"
              value={`${totalPnl >= 0 ? "+" : ""}${totalPnl.toFixed(2)}%`}
              changeType={totalPnl >= 0 ? "positive" : "negative"}
              icon={TrendingUp}
            />
          </div>

          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-xl font-semibold text-foreground">Trading Agents</h2>
                <p className="text-sm text-muted-foreground mt-1">Manage your AI-powered trading agents</p>
              </div>
            </div>

            {agents.length === 0 ? (
              <Card className="flex flex-col items-center justify-center border-dashed p-16 text-center">
                <div className="rounded-full bg-primary/10 p-4 mb-4">
                  <Bot className="h-8 w-8 text-primary" />
                </div>
                <h3 className="text-lg font-semibold text-foreground mb-2">No agents yet</h3>
                <p className="text-sm text-muted-foreground max-w-sm">
                  Create your first AI trading agent to get started with automated trading strategies.
                </p>
              </Card>
            ) : (
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
                {agents.map((agent) => {
                  const model = models.find((m) => m.id === agent.modelId)
                  const exchange = exchanges.find((e) => e.id === agent.exchangeId)
                  return (
                    <AgentCard
                      key={agent.id}
                      agent={agent}
                      modelName={model?.name ?? "Unknown"}
                      exchangeName={exchange?.name ?? "Unknown"}
                      onToggle={() => handleToggleAgent(agent.id)}
                      onDelete={() => handleDeleteAgent(agent.id)}
                    />
                  )
                })}
              </div>
            )}
          </div>
        </div>
      </main>
      <Toaster position="top-right" richColors />
    </div>
  )
}

export default function DashboardPage() {
  console.log("[DashboardPage] Rendering")
  return (
    <ProtectedRoute>
      <DashboardContent />
    </ProtectedRoute>
  )
}
