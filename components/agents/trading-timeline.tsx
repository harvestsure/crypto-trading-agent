"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
  ArrowUpCircle,
  ArrowDownCircle,
  MinusCircle,
  CheckCircle,
  AlertCircle,
  Clock,
  TrendingUp,
  TrendingDown,
  Target,
} from "lucide-react"
import { cn } from "@/lib/utils"

export interface TimelineEvent {
  id: string
  timestamp: number
  type: "signal" | "execution" | "result"
  action: "buy" | "sell" | "hold" | "LONG" | "SHORT" | "CLOSE_LONG" | "CLOSE_SHORT" | "HOLD"
  reason?: string
  confidence?: number
  price?: number
  takeProfit?: number
  stopLoss?: number
  executionStatus?: "pending" | "executed" | "failed"
  pnl?: number
  pnlPercent?: number
  positionSize?: number
  symbol?: string
}

interface TradingTimelineProps {
  events: TimelineEvent[]
  maxHeight?: string
}

export function TradingTimeline({ events, maxHeight = "600px" }: TradingTimelineProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null)

  const getActionIcon = (action: string) => {
    const actionLower = action.toLowerCase()
    if (actionLower === "buy" || actionLower === "long") {
      return <ArrowUpCircle className="h-5 w-5 text-success" />
    } else if (actionLower === "sell" || actionLower === "short") {
      return <ArrowDownCircle className="h-5 w-5 text-destructive" />
    } else if (actionLower === "hold") {
      return <MinusCircle className="h-5 w-5 text-muted-foreground" />
    } else if (actionLower.includes("close")) {
      return <Target className="h-4 w-4 text-warning" />
    }
    return <Clock className="h-4 w-4 text-muted-foreground" />
  }

  const getEventBadgeColor = (type: string, action: string) => {
    const actionLower = action.toLowerCase()

    if (type === "signal") {
      return "bg-blue/20 text-blue border-blue/30"
    } else if (type === "execution") {
      if (actionLower === "buy" || actionLower === "long") {
        return "bg-success/20 text-success border-success/30"
      } else if (actionLower === "sell" || actionLower === "short") {
        return "bg-destructive/20 text-destructive border-destructive/30"
      }
      return "bg-warning/20 text-warning border-warning/30"
    } else if (type === "result") {
      return "bg-purple/20 text-purple border-purple/30"
    }
    return "bg-muted border-border"
  }

  const getStatusIcon = (status?: string) => {
    switch (status) {
      case "executed":
        return <CheckCircle className="h-4 w-4 text-success" />
      case "failed":
        return <AlertCircle className="h-4 w-4 text-destructive" />
      case "pending":
        return <Clock className="h-4 w-4 text-muted-foreground" />
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

  const getTypeLabel = (type: string) => {
    switch (type) {
      case "signal":
        return "Signal"
      case "execution":
        return "Execution"
      case "result":
        return "Result"
      default:
        return type
    }
  }

  const sortedEvents = [...events].sort((a, b) => b.timestamp - a.timestamp)

  // Group events by related signal/execution/result
  const groupedEvents: Record<string, TimelineEvent[]> = {}
  const eventOrder: string[] = []

  sortedEvents.forEach((event) => {
    const key = `${event.timestamp}-${event.action}`
    if (!groupedEvents[key]) {
      groupedEvents[key] = []
      eventOrder.push(key)
    }
    groupedEvents[key].push(event)
  })

  return (
    <Card className="max-h-200 flex flex-col">
      <CardHeader className="pb-3 shrink-0">
        <CardTitle className="text-base flex items-center justify-between">
          <span>Trading Timeline</span>
          <Badge variant="outline" className="text-xs">
            {events.length} events
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="flex-1 min-h-0 overflow-hidden p-0">
        <ScrollArea className="h-full">
          <div className="space-y-4 p-4">
            {sortedEvents.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-center">
                <AlertCircle className="h-8 w-8 text-muted-foreground mb-2" />
                <p className="text-sm text-muted-foreground">No trading history yet</p>
              </div>
            ) : (
              sortedEvents.map((event) => (
                <div key={event.id} className="space-y-2">
                  <div
                    className={cn(
                      "rounded-lg border p-4 space-y-3 cursor-pointer transition-colors hover:bg-muted/50",
                      getEventBadgeColor(event.type, event.action),
                    )}
                    onClick={() => setExpandedId(expandedId === event.id ? null : event.id)}
                  >
                    {/* Header */}
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex items-start gap-3 flex-1">
                        <div className="shrink-0 pt-0.5">{getActionIcon(event.action)}</div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <Badge
                              variant="secondary"
                              className={cn(
                                "text-xs font-semibold",
                                getEventBadgeColor(event.type, event.action),
                              )}
                            >
                              {getTypeLabel(event.type)}
                            </Badge>
                            <Badge
                              variant="outline"
                              className="text-xs capitalize"
                            >
                              {event.action.replace(/_/g, " ")}
                            </Badge>
                            {event.executionStatus && getStatusIcon(event.executionStatus)}
                          </div>
                        </div>
                      </div>
                      <span className="text-xs text-muted-foreground shrink-0">
                        {formatTime(event.timestamp)}
                      </span>
                    </div>

                    {/* Main Info */}
                    <div className="grid grid-cols-2 gap-3 text-sm">
                      {event.price && (
                        <div>
                          <p className="text-xs text-muted-foreground">Price</p>
                          <p className="font-semibold">${event.price.toLocaleString()}</p>
                        </div>
                      )}
                      {event.positionSize && (
                        <div>
                          <p className="text-xs text-muted-foreground">Size</p>
                          <p className="font-semibold">{event.positionSize}</p>
                        </div>
                      )}
                      {event.confidence !== undefined && (
                        <div>
                          <p className="text-xs text-muted-foreground">Confidence</p>
                          <p className="font-semibold">{(event.confidence * 100).toFixed(0)}%</p>
                        </div>
                      )}
                      {event.pnlPercent !== undefined && (
                        <div>
                          <p className="text-xs text-muted-foreground">P&L</p>
                          <p
                            className={cn(
                              "font-semibold",
                              event.pnlPercent >= 0 ? "text-success" : "text-destructive",
                            )}
                          >
                            {event.pnlPercent >= 0 ? "+" : ""}{event.pnlPercent.toFixed(2)}%
                          </p>
                        </div>
                      )}
                    </div>

                    {/* Reason/Details */}
                    {event.reason && (
                      <p className="text-sm text-muted-foreground italic">{event.reason}</p>
                    )}

                    {/* Risk Management */}
                    {(event.takeProfit || event.stopLoss) && (
                      <div className="flex flex-wrap gap-4 text-xs">
                        {event.takeProfit && (
                          <span className="text-success">
                            📈 TP: ${event.takeProfit.toLocaleString()}
                          </span>
                        )}
                        {event.stopLoss && (
                          <span className="text-destructive">
                            📉 SL: ${event.stopLoss.toLocaleString()}
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  )
}
