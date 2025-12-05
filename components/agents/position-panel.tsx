"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { TrendingUp, TrendingDown, DollarSign, Shield, AlertTriangle } from "lucide-react"
import { cn } from "@/lib/utils"
import type { Position, AccountBalance } from "@/lib/types"

interface PositionPanelProps {
  positions: Position[]
  balance: AccountBalance
}

export function PositionPanel({ positions, balance }: PositionPanelProps) {
  const isProfitToday = balance.todayPnl >= 0

  return (
    <div className="space-y-4">
      {/* Account Overview */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base flex items-center gap-2">
            <DollarSign className="h-4 w-4" />
            Account Overview
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
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

          <div className="grid grid-cols-3 gap-3">
            <div className="rounded-lg bg-secondary/50 p-2 text-center">
              <p className="text-xs text-muted-foreground">Today</p>
              <p className={cn("text-sm font-semibold", isProfitToday ? "text-success" : "text-destructive")}>
                {isProfitToday ? "+" : ""}
                {balance.todayPnl.toFixed(2)}%
              </p>
            </div>
            <div className="rounded-lg bg-secondary/50 p-2 text-center">
              <p className="text-xs text-muted-foreground">Week</p>
              <p className={cn("text-sm font-semibold", balance.weekPnl >= 0 ? "text-success" : "text-destructive")}>
                {balance.weekPnl >= 0 ? "+" : ""}
                {balance.weekPnl.toFixed(2)}%
              </p>
            </div>
            <div className="rounded-lg bg-secondary/50 p-2 text-center">
              <p className="text-xs text-muted-foreground">Month</p>
              <p className={cn("text-sm font-semibold", balance.monthPnl >= 0 ? "text-success" : "text-destructive")}>
                {balance.monthPnl >= 0 ? "+" : ""}
                {balance.monthPnl.toFixed(2)}%
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
        </CardContent>
      </Card>

      {/* Open Positions */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base flex items-center justify-between">
            <span className="flex items-center gap-2">
              <Shield className="h-4 w-4" />
              Open Positions
            </span>
            <Badge variant="secondary">{positions.length}</Badge>
          </CardTitle>
        </CardHeader>
        <CardContent>
          {positions.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-4">No open positions</p>
          ) : (
            <div className="space-y-3">
              {positions.map((pos, idx) => (
                <div key={idx} className="rounded-lg border border-border p-3 space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-foreground">{pos.symbol}</span>
                      <Badge variant={pos.side === "long" ? "default" : "destructive"} className="text-xs">
                        {pos.side.toUpperCase()} {pos.leverage}x
                      </Badge>
                    </div>
                    <div
                      className={cn(
                        "flex items-center gap-1 text-sm font-medium",
                        pos.unrealizedPnl >= 0 ? "text-success" : "text-destructive",
                      )}
                    >
                      {pos.unrealizedPnl >= 0 ? (
                        <TrendingUp className="h-3 w-3" />
                      ) : (
                        <TrendingDown className="h-3 w-3" />
                      )}
                      {pos.unrealizedPnl >= 0 ? "+" : ""}
                      {pos.unrealizedPnlPercent.toFixed(2)}%
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div>
                      <span className="text-muted-foreground">Size: </span>
                      <span className="text-foreground">{pos.size}</span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Entry: </span>
                      <span className="text-foreground">${pos.entryPrice.toLocaleString()}</span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Current: </span>
                      <span className="text-foreground">${pos.currentPrice.toLocaleString()}</span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">PnL: </span>
                      <span className={cn(pos.unrealizedPnl >= 0 ? "text-success" : "text-destructive")}>
                        ${pos.unrealizedPnl.toLocaleString()}
                      </span>
                    </div>
                  </div>

                  <div className="flex items-center gap-1 text-xs text-warning">
                    <AlertTriangle className="h-3 w-3" />
                    <span>Liq: ${pos.liquidationPrice.toLocaleString()}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
