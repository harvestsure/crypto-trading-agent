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
  const summaryPnl = typeof pnl === "number" ? pnl : 0
  const summaryTrades = typeof totalTrades === "number" ? totalTrades : 0
  const summaryWinRate = typeof winRate === "number" ? winRate : 0
  const summarySignal = lastSignal?.action ?? "—"
  const summaryIsProfitable = typeof isProfitable === "boolean" ? isProfitable : summaryPnl >= 0

  return (
    <Card className="h-full flex flex-col overflow-hidden">
      <CardHeader className="pb-2 shrink-0">
        <CardTitle className="text-sm flex items-center gap-2">
          <DollarSign className="h-4 w-4" />
          Account Overview
        </CardTitle>
      </CardHeader>
      <CardContent className="flex-1 overflow-hidden p-3">
        <div className="space-y-3 h-full overflow-y-auto">
          {/* Performance summary */}
          <div className="grid grid-cols-2 gap-2">
            <div className="rounded-lg bg-secondary/50 p-2">
              <p className="text-xs text-muted-foreground">PnL</p>
              <p className={cn("text-base font-bold", summaryIsProfitable ? "text-success" : "text-destructive")}>
                {summaryIsProfitable ? "+" : ""}{summaryPnl.toFixed(1)}%
              </p>
            </div>
            <div className="rounded-lg bg-secondary/50 p-2">
              <p className="text-xs text-muted-foreground">Trades</p>
              <p className="text-base font-bold text-foreground">{summaryTrades}</p>
            </div>
            <div className="rounded-lg bg-secondary/50 p-2">
              <p className="text-xs text-muted-foreground">Win Rate</p>
              <p className="text-base font-bold text-foreground">{summaryWinRate}%</p>
            </div>
            <div className="rounded-lg bg-secondary/50 p-2">
              <p className="text-xs text-muted-foreground">Signal</p>
              <p className="text-base font-bold text-foreground capitalize truncate">{summarySignal}</p>
            </div>
          </div>

          <div className="h-px bg-border" />

          {/* Balance row */}
          <div className="grid grid-cols-2 gap-2">
            <div>
              <p className="text-xs text-muted-foreground">Total Balance</p>
              <p className="text-sm font-bold text-foreground">
                ${balance.totalBalance.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Available</p>
              <p className="text-sm font-bold text-foreground">
                ${balance.availableBalance.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </p>
            </div>
          </div>

          <div className="h-px bg-border" />

          {/* Period PnL */}
          <div className="grid grid-cols-3 gap-1.5">
            {[
              { label: "Today", value: balance.todayPnl },
              { label: "Week", value: balance.weekPnl },
              { label: "Month", value: balance.monthPnl },
            ].map(({ label, value }) => (
              <div key={label} className="rounded-md bg-secondary/50 p-1.5 text-center">
                <p className="text-xs text-muted-foreground">{label}</p>
                <p className={cn("text-xs font-semibold", value >= 0 ? "text-success" : "text-destructive")}>
                  {value >= 0 ? "+" : ""}{value.toFixed(1)}%
                </p>
              </div>
            ))}
          </div>

          {/* Margin row */}
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div className="flex flex-col gap-0.5">
              <span className="text-muted-foreground">Used Margin</span>
              <span className="font-mono text-foreground">${balance.usedMargin.toLocaleString()}</span>
            </div>
            <div className="flex flex-col gap-0.5">
              <span className="text-muted-foreground">Unrealized PnL</span>
              <span className={cn("font-mono", balance.unrealizedPnl >= 0 ? "text-success" : "text-destructive")}>
                {balance.unrealizedPnl >= 0 ? "+" : ""}${balance.unrealizedPnl.toLocaleString()}
              </span>
            </div>
          </div>

          {/* Open Positions */}
          {positions.length > 0 && (
            <>
              <div className="h-px bg-border" />
              <div>
                <p className="text-xs text-muted-foreground mb-1.5">Positions ({positions.length})</p>
                <div className="space-y-1.5">
                  {positions.map((pos, i) => (
                    <div key={i} className="rounded-md bg-secondary/40 p-2 text-xs">
                      <div className="flex items-center justify-between">
                        <span className="font-mono font-semibold">{pos.symbol}</span>
                        <span className={cn("font-semibold uppercase text-xs", pos.side === "long" ? "text-success" : "text-destructive")}>
                          {pos.side}
                        </span>
                      </div>
                      <div className="flex items-center justify-between mt-0.5 text-muted-foreground">
                        <span>Entry: ${pos.entryPrice.toLocaleString()}</span>
                        <span className={cn(pos.unrealizedPnl >= 0 ? "text-success" : "text-destructive")}>
                          {pos.unrealizedPnl >= 0 ? "+" : ""}${pos.unrealizedPnl.toFixed(2)}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
