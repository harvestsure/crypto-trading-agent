"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import { cn } from "@/lib/utils"
import { Brain, TrendingUp, TrendingDown, Target, AlertTriangle, CheckCircle2 } from "lucide-react"
import type { TradingAction } from "./action-history"

interface AITradingSummaryProps {
  actions: TradingAction[]
  currentPositions?: number
}

export function AITradingSummary({ actions, currentPositions = 0 }: AITradingSummaryProps) {
  // Calculate statistics
  const totalActions = actions.length
  const executedActions = actions.filter((a) => a.result?.status === "executed").length
  const longActions = actions.filter((a) => a.action === "LONG").length
  const shortActions = actions.filter((a) => a.action === "SHORT").length
  const holdActions = actions.filter((a) => a.action === "HOLD").length

  // Calculate P&L from executed actions
  const executedWithPnL = actions.filter((a) => a.result?.status === "executed" && a.result?.pnl !== undefined)
  const totalPnL = executedWithPnL.reduce((sum, a) => sum + (a.result?.pnl ?? 0), 0)
  const winningTrades = executedWithPnL.filter((a) => (a.result?.pnl ?? 0) > 0).length
  const winRate = executedWithPnL.length > 0 ? (winningTrades / executedWithPnL.length) * 100 : 0

  // Calculate average confidence
  const avgConfidence = actions.length > 0 ? actions.reduce((sum, a) => sum + a.confidence, 0) / actions.length : 0

  // Last action
  const lastAction = actions.length > 0 ? actions[0] : null

  // Signal distribution
  const longPercent = totalActions > 0 ? (longActions / totalActions) * 100 : 0
  const shortPercent = totalActions > 0 ? (shortActions / totalActions) * 100 : 0
  const holdPercent = totalActions > 0 ? (holdActions / totalActions) * 100 : 0

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base flex items-center gap-2">
          <Brain className="h-4 w-4 text-primary" />
          AI Trading Performance
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Key Metrics */}
        <div className="grid grid-cols-2 gap-3">
          <div className="rounded-lg bg-muted p-3">
            <div className="text-xs text-muted-foreground mb-1">Total Signals</div>
            <div className="text-2xl font-bold">{totalActions}</div>
            <div className="text-xs text-muted-foreground">{executedActions} executed</div>
          </div>

          <div className="rounded-lg bg-muted p-3">
            <div className="text-xs text-muted-foreground mb-1">Win Rate</div>
            <div className={cn("text-2xl font-bold", winRate >= 50 ? "text-success" : "text-destructive")}>
              {winRate.toFixed(0)}%
            </div>
            <div className="text-xs text-muted-foreground">
              {winningTrades}/{executedWithPnL.length} trades
            </div>
          </div>

          <div className="rounded-lg bg-muted p-3">
            <div className="text-xs text-muted-foreground mb-1">Total P&L</div>
            <div className={cn("text-2xl font-bold", totalPnL >= 0 ? "text-success" : "text-destructive")}>
              {totalPnL >= 0 ? "+" : ""}${totalPnL.toFixed(2)}
            </div>
            <div className="text-xs text-muted-foreground">From AI signals</div>
          </div>

          <div className="rounded-lg bg-muted p-3">
            <div className="text-xs text-muted-foreground mb-1">Avg Confidence</div>
            <div className="text-2xl font-bold">{(avgConfidence * 100).toFixed(0)}%</div>
            <div className="text-xs text-muted-foreground">All signals</div>
          </div>
        </div>



        {/* Last Signal */}
        {lastAction && (
          <div className="rounded-lg border border-border p-3 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground">Last Signal</span>
              <Badge
                variant={
                  lastAction.action === "LONG" || lastAction.action === "SHORT" ? "default" : "secondary"
                }
              >
                {lastAction.action}
              </Badge>
            </div>
            <div className="flex items-center gap-2">
              {lastAction.result?.status === "executed" && (
                <CheckCircle2 className="h-3 w-3 text-success" />
              )}
              {lastAction.result?.status === "pending" && (
                <AlertTriangle className="h-3 w-3 text-warning" />
              )}
              <span className="text-xs">
                {new Date(lastAction.timestamp).toLocaleString()} • {lastAction.symbol}
              </span>
            </div>
            <div className="text-xs text-muted-foreground">
              Confidence: {(lastAction.confidence * 100).toFixed(0)}%
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
