"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"
import {
  TrendingUp,
  TrendingDown,
  Target,
  Minus,
  Clock,
  DollarSign,
  Percent,
  AlertCircle,
} from "lucide-react"
import { cn } from "@/lib/utils"

export interface TradingAction {
  id: string
  timestamp: number
  action: "LONG" | "SHORT" | "CLOSE_LONG" | "CLOSE_SHORT" | "HOLD"
  symbol: string
  confidence: number
  reasoning: string
  price?: number
  positionSize?: number
  stopLoss?: number
  takeProfit?: number
  result?: {
    status: "pending" | "executed" | "failed"
    pnl?: number
    pnlPercent?: number
  }
}

interface ActionHistoryProps {
  actions: TradingAction[]
  maxHeight?: string
}

export function ActionHistory({ actions, maxHeight = "600px" }: ActionHistoryProps) {
  const getActionIcon = (action: string) => {
    switch (action) {
      case "LONG":
        return <TrendingUp className="h-4 w-4" />
      case "SHORT":
        return <TrendingDown className="h-4 w-4" />
      case "CLOSE_LONG":
      case "CLOSE_SHORT":
        return <Target className="h-4 w-4" />
      default:
        return <Minus className="h-4 w-4" />
    }
  }

  const getActionColor = (action: string) => {
    switch (action) {
      case "LONG":
        return "text-success"
      case "SHORT":
        return "text-destructive"
      case "CLOSE_LONG":
      case "CLOSE_SHORT":
        return "text-warning"
      default:
        return "text-muted-foreground"
    }
  }

  const getActionBgColor = (action: string) => {
    switch (action) {
      case "LONG":
        return "bg-success/10 border-success/20"
      case "SHORT":
        return "bg-destructive/10 border-destructive/20"
      case "CLOSE_LONG":
      case "CLOSE_SHORT":
        return "bg-warning/10 border-warning/20"
      default:
        return "bg-muted border-border"
    }
  }

  const getStatusBadge = (status?: string) => {
    switch (status) {
      case "executed":
        return (
          <Badge variant="default" className="text-xs bg-success text-success-foreground">
            Executed
          </Badge>
        )
      case "failed":
        return (
          <Badge variant="default" className="text-xs bg-destructive text-destructive-foreground">
            Failed
          </Badge>
        )
      case "pending":
        return (
          <Badge variant="secondary" className="text-xs">
            Pending
          </Badge>
        )
      default:
        return null
    }
  }

  const formatTime = (timestamp: number) => {
    const date = new Date(timestamp)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffMins = Math.floor(diffMs / 60000)

    if (diffMins < 1) return "Just now"
    if (diffMins < 60) return `${diffMins}m ago`

    const diffHours = Math.floor(diffMins / 60)
    if (diffHours < 24) return `${diffHours}h ago`

    const diffDays = Math.floor(diffHours / 24)
    return `${diffDays}d ago`
  }

  const sortedActions = [...actions].sort((a, b) => b.timestamp - a.timestamp)

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base flex items-center justify-between">
          <span>Trading Action History</span>
          <Badge variant="outline" className="text-xs">
            {actions.length} total
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <ScrollArea className="pr-4" style={{ maxHeight }}>
          <div className="space-y-3">
            {sortedActions.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-center">
                <AlertCircle className="h-8 w-8 text-muted-foreground mb-2" />
                <p className="text-sm text-muted-foreground">No trading actions yet</p>
              </div>
            ) : (
              sortedActions.map((action, index) => (
                <div key={action.id}>
                  <div className={cn("rounded-lg border p-4 space-y-3", getActionBgColor(action.action))}>
                    {/* Header */}
                    <div className="flex items-start justify-between">
                      <div className="flex items-center gap-2">
                        <div className={cn("p-1.5 rounded", getActionColor(action.action))}>
                          {getActionIcon(action.action)}
                        </div>
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="font-semibold text-sm">{action.action.replace("_", " ")}</span>
                            {action.result && getStatusBadge(action.result.status)}
                          </div>
                          <span className="text-xs text-muted-foreground">{action.symbol}</span>
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="flex items-center gap-1 text-xs text-muted-foreground">
                          <Clock className="h-3 w-3" />
                          {formatTime(action.timestamp)}
                        </div>
                        <div className="text-xs text-muted-foreground mt-0.5">
                          {new Date(action.timestamp).toLocaleTimeString()}
                        </div>
                      </div>
                    </div>

                    {/* Price & Confidence */}
                    <div className="grid grid-cols-2 gap-3 text-xs">
                      {action.price && (
                        <div className="flex items-center gap-1.5">
                          <DollarSign className="h-3 w-3 text-muted-foreground" />
                          <span className="text-muted-foreground">Price:</span>
                          <span className="font-semibold">${action.price.toLocaleString()}</span>
                        </div>
                      )}
                      <div className="flex items-center gap-1.5">
                        <Percent className="h-3 w-3 text-muted-foreground" />
                        <span className="text-muted-foreground">Confidence:</span>
                        <span
                          className={cn(
                            "font-semibold",
                            action.confidence >= 0.7 ? "text-success" : action.confidence >= 0.4 ? "text-warning" : "text-destructive",
                          )}
                        >
                          {(action.confidence * 100).toFixed(0)}%
                        </span>
                      </div>
                    </div>

                    {/* Position Details */}
                    {(action.positionSize || action.stopLoss || action.takeProfit) && (
                      <div className="grid grid-cols-3 gap-2 text-xs">
                        {action.positionSize && (
                          <div className="bg-background/50 rounded p-2">
                            <div className="text-muted-foreground mb-0.5">Size</div>
                            <div className="font-semibold">{action.positionSize}%</div>
                          </div>
                        )}
                        {action.stopLoss && (
                          <div className="bg-background/50 rounded p-2">
                            <div className="text-destructive mb-0.5">Stop Loss</div>
                            <div className="font-semibold">${action.stopLoss.toLocaleString()}</div>
                          </div>
                        )}
                        {action.takeProfit && (
                          <div className="bg-background/50 rounded p-2">
                            <div className="text-success mb-0.5">Take Profit</div>
                            <div className="font-semibold">${action.takeProfit.toLocaleString()}</div>
                          </div>
                        )}
                      </div>
                    )}

                    {/* PnL Result */}
                    {action.result && action.result.pnl !== undefined && (
                      <div
                        className={cn(
                          "flex items-center justify-between p-2 rounded",
                          action.result.pnl >= 0
                            ? "bg-success/20 border border-success/30"
                            : "bg-destructive/20 border border-destructive/30",
                        )}
                      >
                        <span className="text-xs font-medium">P&L</span>
                        <div className="text-right">
                          <div
                            className={cn(
                              "font-bold text-sm",
                              action.result.pnl >= 0 ? "text-success" : "text-destructive",
                            )}
                          >
                            {action.result.pnl >= 0 ? "+" : ""}${action.result.pnl.toFixed(2)}
                          </div>
                          {action.result.pnlPercent !== undefined && (
                            <div
                              className={cn(
                                "text-xs",
                                action.result.pnl >= 0 ? "text-success" : "text-destructive",
                              )}
                            >
                              {action.result.pnl >= 0 ? "+" : ""}
                              {action.result.pnlPercent.toFixed(2)}%
                            </div>
                          )}
                        </div>
                      </div>
                    )}

                    {/* Reasoning */}
                    <div className="text-xs text-muted-foreground leading-relaxed pt-2 border-t border-border/50">
                      {action.reasoning}
                    </div>
                  </div>

                  {index < sortedActions.length - 1 && <Separator className="my-3" />}
                </div>
              ))
            )}
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  )
}
