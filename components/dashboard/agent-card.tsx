"use client"

import { Play, Pause, MoreVertical, TrendingUp, TrendingDown, Activity } from "lucide-react"
import { Button } from "@/components/ui/button"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import type { TradingAgent } from "@/lib/types"
import Link from "next/link"

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
    <div className="group relative rounded-xl border border-border bg-card p-5 transition-all hover:border-primary/40 hover:shadow-lg hover:shadow-primary/5">
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3 flex-1 min-w-0">
          <div
            className={cn(
              "flex h-11 w-11 shrink-0 items-center justify-center rounded-lg transition-all",
              isRunning ? "bg-success/15 ring-1 ring-success/20" : "bg-secondary",
            )}
          >
            <div
              className={cn(
                "h-3 w-3 rounded-full transition-all",
                isRunning ? "animate-pulse bg-success shadow-lg shadow-success/50" : "bg-muted-foreground",
              )}
            />
          </div>
          <div className="flex-1 min-w-0">
            <Link href={`/agents/${agent.id}`}>
              <h3 className="font-semibold text-foreground hover:text-primary transition-colors truncate">
                {agent.name}
              </h3>
            </Link>
            <p className="text-sm text-muted-foreground truncate">{agent.symbol}</p>
          </div>
        </div>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon" className="h-8 w-8 shrink-0">
              <MoreVertical className="h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onClick={onToggle}>{isRunning ? "Pause Agent" : "Start Agent"}</DropdownMenuItem>
            <DropdownMenuItem asChild>
              <Link href={`/agents/${agent.id}`}>View Details</Link>
            </DropdownMenuItem>
            <DropdownMenuItem className="text-destructive" onClick={onDelete}>
              Delete Agent
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      <div className="flex flex-wrap gap-1.5 mb-4">
        <Badge variant="secondary" className="text-xs font-medium">
          {modelName}
        </Badge>
        <Badge variant="secondary" className="text-xs font-medium">
          {exchangeName}
        </Badge>
        <Badge variant="secondary" className="text-xs font-medium">
          {agent.timeframe}
        </Badge>
      </div>

      <div className="grid grid-cols-3 gap-3 border-t border-border pt-4 mb-4">
        <div>
          <p className="text-xs text-muted-foreground mb-1">Trades</p>
          <p className="text-base font-semibold text-foreground tabular-nums">{agent.performance?.totalTrades ?? 0}</p>
        </div>
        <div>
          <p className="text-xs text-muted-foreground mb-1">Win Rate</p>
          <p className="text-base font-semibold text-foreground tabular-nums">{agent.performance?.winRate ?? 0}%</p>
        </div>
        <div>
          <p className="text-xs text-muted-foreground mb-1">PnL</p>
          <p
            className={cn(
              "flex items-center gap-1 text-base font-semibold tabular-nums",
              isProfitable ? "text-success" : "text-destructive",
            )}
          >
            {isProfitable ? <TrendingUp className="h-3.5 w-3.5" /> : <TrendingDown className="h-3.5 w-3.5" />}
            {isProfitable ? "+" : ""}
            {pnl.toFixed(2)}%
          </p>
        </div>
      </div>

      <Button variant={isRunning ? "secondary" : "default"} size="sm" className="w-full" onClick={onToggle}>
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

      {isRunning && (
        <div className="absolute top-3 right-3 flex items-center gap-1.5 text-xs text-success">
          <Activity className="h-3 w-3 animate-pulse" />
          <span className="font-medium">Active</span>
        </div>
      )}
    </div>
  )
}
