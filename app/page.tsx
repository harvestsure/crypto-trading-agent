"use client"

import { useAppStore } from "@/lib/store"
import { Sidebar } from "@/components/layout/sidebar"
import { Header } from "@/components/layout/header"
import { StatsCard } from "@/components/dashboard/stats-card"
import { AgentCard } from "@/components/dashboard/agent-card"
import { Bot, Brain, Building2, TrendingUp } from "lucide-react"

export default function DashboardPage() {
  const { models, exchanges, agents, updateAgent, deleteAgent } = useAppStore()

  const runningAgents = agents.filter((a) => a.status === "running").length
  const totalPnl = agents.reduce((acc, a) => acc + (a.performance?.pnl ?? 0), 0)

  const handleToggleAgent = (agentId: string) => {
    const agent = agents.find((a) => a.id === agentId)
    if (agent) {
      updateAgent(agentId, {
        status: agent.status === "running" ? "paused" : "running",
      })
    }
  }

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="flex-1 pl-64">
        <Header title="Dashboard" description="Overview of your trading agents and performance" />

        <div className="p-6">
          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
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

          <div className="mt-8">
            <h2 className="mb-4 text-lg font-semibold text-foreground">Trading Agents</h2>
            {agents.length === 0 ? (
              <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-border bg-card p-12 text-center">
                <Bot className="h-12 w-12 text-muted-foreground" />
                <h3 className="mt-4 text-lg font-semibold text-foreground">No agents yet</h3>
                <p className="mt-2 text-sm text-muted-foreground">Create your first AI trading agent to get started.</p>
              </div>
            ) : (
              <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
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
                      onDelete={() => deleteAgent(agent.id)}
                    />
                  )
                })}
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  )
}
