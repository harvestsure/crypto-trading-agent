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
      <CardHeader className="py-2 px-3 shrink-0">
        <CardTitle className="text-xs flex items-center gap-1.5 text-muted-foreground uppercase tracking-wide">
          <DollarSign className="h-3.5 w-3.5" />
          Account Overview
        </CardTitle>
      </CardHeader>
      <CardContent className="flex-1 min-h-0 p-3 pt-0">
        <div className="flex flex-col gap-2 h-full overflow-y-auto pr-0.5">

          {/* 4-stat grid */}
          <div className="grid grid-cols-2 gap-1.5">
            {[
              { label: "PnL", value: `${summaryIsProfitable ? "+" : ""}${summaryPnl.toFixed(1)}%`, color: summaryIsProfitable ? "text-success" : "text-destructive" },
              { label: "Trades", value: String(summaryTrades), color: "text-foreground" },
              { label: "Win Rate", value: `${summaryWinRate}%`, color: "text-foreground" },
              { label: "Signal", value: summarySignal, color: "text-foreground" },
            ].map(({ label, value, color }) => (
              <div key={label} className="rounded-md bg-secondary/50 px-2 py-1.5">
                <p className="text-[10px] text-muted-foreground leading-none mb-0.5">{label}</p>
                <p className={cn("text-sm font-bold leading-none truncate", color)}>{value}</p>
              </div>
            ))}
          </div>

          <div className="h-px bg-border shrink-0" />

          {/* Balance */}
          <div className="grid grid-cols-2 gap-1.5">
            <div className="rounded-md bg-secondary/40 px-2 py-1.5">
              <p className="text-[10px] text-muted-foreground leading-none mb-0.5">Total Balance</p>
              <p className="text-xs font-bold text-foreground font-mono">
                ${balance.totalBalance.toLocaleString(undefined, { maximumFractionDigits: 0 })}
              </p>
            </div>
            <div className="rounded-md bg-secondary/40 px-2 py-1.5">
              <p className="text-[10px] text-muted-foreground leading-none mb-0.5">Available</p>
              <p className="text-xs font-bold text-foreground font-mono">
                ${balance.availableBalance.toLocaleString(undefined, { maximumFractionDigits: 0 })}
              </p>
            </div>
          </div>

          {/* Period PnL row */}
          <div className="grid grid-cols-3 gap-1">
            {[
              { label: "Today", value: balance.todayPnl },
              { label: "Week",  value: balance.weekPnl },
              { label: "Month", value: balance.monthPnl },
            ].map(({ label, value }) => (
              <div key={label} className="rounded-md bg-secondary/50 p-1 text-center">
                <p className="text-[10px] text-muted-foreground leading-none mb-0.5">{label}</p>
                <p className={cn("text-[10px] font-semibold leading-none", value >= 0 ? "text-success" : "text-destructive")}>
                  {value >= 0 ? "+" : ""}{value.toFixed(1)}%
                </p>
              </div>
            ))}
          </div>

          {/* Open Positions */}
          {positions.length > 0 && (
            <>
              <div className="h-px bg-border shrink-0" />
              <div className="shrink-0">
                <p className="text-[10px] text-muted-foreground mb-1 uppercase tracking-wide">Positions ({positions.length})</p>
                <div className="flex flex-col gap-1">
                  {positions.map((pos, i) => (
                    <div key={i} className="rounded-md bg-secondary/40 px-2 py-1 text-xs flex items-center justify-between gap-1">
                      <span className="font-mono font-semibold truncate">{pos.symbol}</span>
                      <span className={cn("uppercase text-[10px] font-bold shrink-0", pos.side === "long" ? "text-success" : "text-destructive")}>
                        {pos.side}
                      </span>
                      <span className={cn("font-mono text-[10px] shrink-0", pos.unrealizedPnl >= 0 ? "text-success" : "text-destructive")}>
                        {pos.unrealizedPnl >= 0 ? "+" : ""}${pos.unrealizedPnl.toFixed(1)}
                      </span>
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
