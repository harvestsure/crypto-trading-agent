"use client"

import { Play, Pause, MoreVertical, TrendingUp, TrendingDown } from "lucide-react"
import { Button } from "@/components/ui/button"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import type { TradingAgent } from "@/lib/types"

interface AgentCardProps {
  agent: TradingAgent
  modelName: string
  exchangeName: string
  onToggle: () => void
  onDelete: () => void
}

export function AgentCard({ agent, modelName, exchangeName, onToggle, onDelete }: AgentCardProps) {
  const isRunning = agent.status === "running"
  const pnl = agent.performance?.pnl ?? 0
  const isProfitable = pnl >= 0

  return (
    <div className="rounded-xl border border-border bg-card p-5 transition-all hover:border-primary/50">
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div
            className={cn(
              "flex h-10 w-10 items-center justify-center rounded-lg",
              isRunning ? "bg-success/20" : "bg-secondary",
            )}
          >
            <div
              className={cn("h-3 w-3 rounded-full", isRunning ? "animate-pulse bg-success" : "bg-muted-foreground")}
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
            <DropdownMenuItem onClick={onToggle}>{isRunning ? "Pause Agent" : "Start Agent"}</DropdownMenuItem>
            <DropdownMenuItem className="text-destructive" onClick={onDelete}>
              Delete Agent
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        <Badge variant="secondary" className="text-xs">
          {modelName}
        </Badge>
        <Badge variant="secondary" className="text-xs">
          {exchangeName}
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
        <Button variant={isRunning ? "secondary" : "default"} size="sm" className="flex-1" onClick={onToggle}>
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
      </div>
    </div>
  )
}
