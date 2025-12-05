"use client"

import { useState } from "react"
import Link from "next/link"
import { useAppStore } from "@/lib/store"
import { Sidebar } from "@/components/layout/sidebar"
import { Header } from "@/components/layout/header"
import { CreateAgentModal } from "@/components/modals/create-agent-modal"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Plus, Bot, AlertCircle, Play, Pause, MoreVertical, ExternalLink, TrendingUp, TrendingDown } from "lucide-react"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { cn } from "@/lib/utils"

export default function AgentsPage() {
  const { agents, models, exchanges, updateAgent, deleteAgent } = useAppStore()
  const [isCreateOpen, setIsCreateOpen] = useState(false)

  const canCreateAgent = models.length > 0 && exchanges.length > 0

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
        <Header title="Trading Agents" description="Create and manage your AI trading agents" />

        <div className="p-6">
          {!canCreateAgent && (
            <Alert className="mb-6 border-warning/50 bg-warning/10">
              <AlertCircle className="h-4 w-4 text-warning" />
              <AlertTitle className="text-warning">Setup Required</AlertTitle>
              <AlertDescription className="text-warning/80">
                You need to add at least one AI model and one exchange before creating agents.
              </AlertDescription>
            </Alert>
          )}

          <div className="mb-6 flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">
                {agents.length} agent{agents.length !== 1 ? "s" : ""} configured
              </p>
            </div>
            <Button onClick={() => setIsCreateOpen(true)} disabled={!canCreateAgent}>
              <Plus className="mr-2 h-4 w-4" />
              Create Agent
            </Button>
          </div>

          {agents.length === 0 ? (
            <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-border bg-card p-12 text-center">
              <Bot className="h-12 w-12 text-muted-foreground" />
              <h3 className="mt-4 text-lg font-semibold text-foreground">No agents created</h3>
              <p className="mt-2 text-sm text-muted-foreground">
                Create your first AI trading agent to start automated trading.
              </p>
              <Button className="mt-4" onClick={() => setIsCreateOpen(true)} disabled={!canCreateAgent}>
                <Plus className="mr-2 h-4 w-4" />
                Create Agent
              </Button>
            </div>
          ) : (
            <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
              {agents.map((agent) => {
                const model = models.find((m) => m.id === agent.modelId)
                const exchange = exchanges.find((e) => e.id === agent.exchangeId)
                const isRunning = agent.status === "running"
                const pnl = agent.performance?.pnl ?? 0
                const isProfitable = pnl >= 0

                return (
                  <div
                    key={agent.id}
                    className="rounded-xl border border-border bg-card p-5 transition-all hover:border-primary/50"
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex items-center gap-3">
                        <div
                          className={cn(
                            "flex h-10 w-10 items-center justify-center rounded-lg",
                            isRunning ? "bg-success/20" : "bg-secondary",
                          )}
                        >
                          <div
                            className={cn(
                              "h-3 w-3 rounded-full",
                              isRunning ? "animate-pulse bg-success" : "bg-muted-foreground",
                            )}
                          />
                        </div>
                        <div>
                          <h3 className="font-semibold text-foreground">{agent.name}</h3>
                          <p className="text-sm text-muted-foreground">{agent.symbol}</p>
                        </div>
                      </div>

                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="icon" className="h-8 w-8">
                            <MoreVertical className="h-4 w-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem asChild>
                            <Link href={`/agents/${agent.id}`}>
                              <ExternalLink className="mr-2 h-4 w-4" />
                              View Details
                            </Link>
                          </DropdownMenuItem>
                          <DropdownMenuItem onClick={() => handleToggleAgent(agent.id)}>
                            {isRunning ? (
                              <>
                                <Pause className="mr-2 h-4 w-4" />
                                Pause Agent
                              </>
                            ) : (
                              <>
                                <Play className="mr-2 h-4 w-4" />
                                Start Agent
                              </>
                            )}
                          </DropdownMenuItem>
                          <DropdownMenuItem className="text-destructive" onClick={() => deleteAgent(agent.id)}>
                            Delete Agent
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </div>

                    <div className="mt-4 flex flex-wrap gap-2">
                      <Badge variant="secondary" className="text-xs">
                        {model?.name ?? "Unknown"}
                      </Badge>
                      <Badge variant="secondary" className="text-xs">
                        {exchange?.name ?? "Unknown"}
                      </Badge>
                      <Badge variant="secondary" className="text-xs">
                        {agent.timeframe}
                      </Badge>
                    </div>

                    <div className="mt-4 grid grid-cols-3 gap-4 border-t border-border pt-4">
                      <div>
                        <p className="text-xs text-muted-foreground">Trades</p>
                        <p className="text-sm font-semibold text-foreground">{agent.performance?.totalTrades ?? 0}</p>
                      </div>
                      <div>
                        <p className="text-xs text-muted-foreground">Win Rate</p>
                        <p className="text-sm font-semibold text-foreground">{agent.performance?.winRate ?? 0}%</p>
                      </div>
                      <div>
                        <p className="text-xs text-muted-foreground">PnL</p>
                        <p
                          className={cn(
                            "flex items-center gap-1 text-sm font-semibold",
                            isProfitable ? "text-success" : "text-destructive",
                          )}
                        >
                          {isProfitable ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
                          {isProfitable ? "+" : ""}
                          {pnl.toFixed(2)}%
                        </p>
                      </div>
                    </div>

                    <div className="mt-4 flex gap-2">
                      <Button
                        variant={isRunning ? "secondary" : "default"}
                        size="sm"
                        className="flex-1"
                        onClick={() => handleToggleAgent(agent.id)}
                      >
                        {isRunning ? (
                          <>
                            <Pause className="mr-2 h-4 w-4" /> Pause
                          </>
                        ) : (
                          <>
                            <Play className="mr-2 h-4 w-4" /> Start
                          </>
                        )}
                      </Button>
                      <Button variant="outline" size="sm" asChild>
                        <Link href={`/agents/${agent.id}`}>
                          <ExternalLink className="mr-2 h-4 w-4" /> Details
                        </Link>
                      </Button>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>

        <CreateAgentModal open={isCreateOpen} onOpenChange={setIsCreateOpen} />
      </main>
    </div>
  )
}
