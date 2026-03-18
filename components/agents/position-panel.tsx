"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { DollarSign } from "lucide-react"
import { cn } from "@/lib/utils"
import type { Position, AccountBalance } from "@/lib/types"

interface PositionPanelProps {
  positions: Position[]
  balance: AccountBalance
  agentId?: string
  pnl?: number
  totalTrades?: number
  winRate?: number
  lastSignal?: { action?: string }
  isProfitable?: boolean
}

export function PositionPanel({
  positions,
  balance,
  agentId,
  pnl,
  totalTrades,
  winRate,
  lastSignal,
  isProfitable,
}: PositionPanelProps) {
  const isProfitToday = balance.todayPnl >= 0

  const summaryPnl = typeof pnl === "number" ? pnl : 0
  const summaryTrades = typeof totalTrades === "number" ? totalTrades : 0
  const summaryWinRate = typeof winRate === "number" ? winRate : 0
  const summarySignal = lastSignal?.action ?? "—"
  const summaryIsProfitable = typeof isProfitable === "boolean" ? isProfitable : summaryPnl >= 0

  return (
    <div className="h-full">
      <Card className="h-full">
        <CardHeader className="pb-2">
          <CardTitle className="text-base flex items-center gap-2">
            <DollarSign className="h-4 w-4" />
            Account Overview
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Performance summary */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <p className="text-xs text-muted-foreground">PnL</p>
              <p className={cn("text-lg font-bold", summaryIsProfitable ? "text-success" : "text-destructive")}>
                {summaryIsProfitable ? "+" : ""}{summaryPnl.toFixed(1)}%
              </p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Trades</p>
              <p className="text-lg font-bold text-foreground">{summaryTrades}</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Win Rate</p>
              <p className="text-lg font-bold text-foreground">{summaryWinRate}%</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Signal</p>
              <p className="text-lg font-bold text-foreground capitalize truncate">
                {summarySignal}
              </p>
            </div>
          </div>

          <div className="h-px bg-border" />

          {/* Balance */}
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1">
              <p className="text-xs text-muted-foreground">Total Balance</p>
              <p className="text-xl font-bold text-foreground">
                ${balance.totalBalance.toLocaleString(undefined, { minimumFractionDigits: 2 })}
              </p>
            </div>
            <div className="space-y-1">
              <p className="text-xs text-muted-foreground">Available</p>
              <p className="text-xl font-bold text-foreground">
                ${balance.availableBalance.toLocaleString(undefined, { minimumFractionDigits: 2 })}
              </p>
            </div>
          </div>

          <div className="h-px bg-border" />

          {/* Period PnL */}
          <div className="grid grid-cols-3 gap-2">
            <div className="rounded-lg bg-secondary/50 p-2 text-center">
              <p className="text-xs text-muted-foreground">Today</p>
              <p className={cn("text-sm font-semibold", isProfitToday ? "text-success" : "text-destructive")}>
                {isProfitToday ? "+" : ""}{balance.todayPnl.toFixed(2)}%
              </p>
            </div>
            <div className="rounded-lg bg-secondary/50 p-2 text-center">
              <p className="text-xs text-muted-foreground">Week</p>
              <p className={cn("text-sm font-semibold", balance.weekPnl >= 0 ? "text-success" : "text-destructive")}>
                {balance.weekPnl >= 0 ? "+" : ""}{balance.weekPnl.toFixed(2)}%
              </p>
            </div>
            <div className="rounded-lg bg-secondary/50 p-2 text-center">
              <p className="text-xs text-muted-foreground">Month</p>
              <p className={cn("text-sm font-semibold", balance.monthPnl >= 0 ? "text-success" : "text-destructive")}>
                {balance.monthPnl >= 0 ? "+" : ""}{balance.monthPnl.toFixed(2)}%
              </p>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3 text-sm">
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">Used Margin</span>
              <span className="text-foreground">${balance.usedMargin.toLocaleString()}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">Unrealized PnL</span>
              <span className={cn(balance.unrealizedPnl >= 0 ? "text-success" : "text-destructive")}>
                {balance.unrealizedPnl >= 0 ? "+" : ""}${balance.unrealizedPnl.toLocaleString()}
              </span>
            </div>
          </div>

          {/* Open Positions */}
          {positions.length > 0 && (
            <>
              <div className="h-px bg-border" />
              <div>
                <p className="text-xs text-muted-foreground mb-2">Open Positions ({positions.length})</p>
                <div className="space-y-2">
                  {positions.map((pos, i) => (
                    <div key={i} className="rounded-lg bg-secondary/40 p-2 text-xs">
                      <div className="flex items-center justify-between">
                        <span className="font-mono font-semibold">{pos.symbol}</span>
                        <span className={cn(
                          "font-semibold uppercase",
                          pos.side === "long" ? "text-success" : "text-destructive"
                        )}>
                          {pos.side}
                        </span>
                      </div>
                      <div className="flex items-center justify-between mt-1 text-muted-foreground">
                        <span>Entry: ${pos.entryPrice.toLocaleString()}</span>
                        <span className={cn(
                          pos.unrealizedPnl >= 0 ? "text-success" : "text-destructive"
                        )}>
                          {pos.unrealizedPnl >= 0 ? "+" : ""}${pos.unrealizedPnl.toFixed(2)}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
