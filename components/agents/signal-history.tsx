"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { ArrowUpCircle, ArrowDownCircle, MinusCircle } from "lucide-react"
import { cn } from "@/lib/utils"

interface Signal {
  id: string
  timestamp: Date
  action: "buy" | "sell" | "hold"
  reason: string
  price: number
  takeProfit?: number
  stopLoss?: number
}

interface SignalHistoryProps {
  agentId: string
}

export function SignalHistory({ agentId }: SignalHistoryProps) {
  const [signals, setSignals] = useState<Signal[]>([])

  useEffect(() => {
    // Generate mock signal history
    const mockSignals: Signal[] = [
      {
        id: "1",
        timestamp: new Date(Date.now() - 3600000),
        action: "buy",
        reason: "RSI oversold (28.5), ADX showing strong trend (32.1), KAMA crossed above price",
        price: 42850,
        takeProfit: 44000,
        stopLoss: 42000,
      },
      {
        id: "2",
        timestamp: new Date(Date.now() - 7200000),
        action: "hold",
        reason: "Market consolidating, CHOP index at 58.3, waiting for clearer signal",
        price: 42700,
      },
      {
        id: "3",
        timestamp: new Date(Date.now() - 10800000),
        action: "sell",
        reason: "RSI overbought (72.1), bearish divergence detected, taking profits",
        price: 43200,
        takeProfit: 42000,
        stopLoss: 43500,
      },
      {
        id: "4",
        timestamp: new Date(Date.now() - 14400000),
        action: "buy",
        reason: "Trend reversal confirmed, ADX rising (28.7), price above KAMA",
        price: 42100,
        takeProfit: 43500,
        stopLoss: 41500,
      },
      {
        id: "5",
        timestamp: new Date(Date.now() - 18000000),
        action: "hold",
        reason: "Choppy market conditions (CHOP: 65.2), no clear direction",
        price: 42300,
      },
    ]

    setSignals(mockSignals)
  }, [agentId])

  const getSignalIcon = (action: Signal["action"]) => {
    switch (action) {
      case "buy":
        return <ArrowUpCircle className="h-5 w-5 text-success" />
      case "sell":
        return <ArrowDownCircle className="h-5 w-5 text-destructive" />
      case "hold":
        return <MinusCircle className="h-5 w-5 text-muted-foreground" />
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Signal History</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {signals.map((signal) => (
            <div key={signal.id} className="flex gap-4 rounded-lg border border-border p-4">
              <div className="flex-shrink-0 pt-1">{getSignalIcon(signal.action)}</div>
              <div className="flex-1 space-y-2">
                <div className="flex items-center justify-between">
                  <Badge
                    variant="secondary"
                    className={cn(
                      signal.action === "buy" && "bg-success/20 text-success",
                      signal.action === "sell" && "bg-destructive/20 text-destructive",
                    )}
                  >
                    {signal.action.toUpperCase()}
                  </Badge>
                  <span className="text-xs text-muted-foreground">{signal.timestamp.toLocaleString()}</span>
                </div>
                <p className="text-sm text-foreground">{signal.reason}</p>
                <div className="flex flex-wrap gap-4 text-xs text-muted-foreground">
                  <span>Price: ${signal.price.toLocaleString()}</span>
                  {signal.takeProfit && <span className="text-success">TP: ${signal.takeProfit.toLocaleString()}</span>}
                  {signal.stopLoss && <span className="text-destructive">SL: ${signal.stopLoss.toLocaleString()}</span>}
                </div>
              </div>
            </div>
          ))}

          {signals.length === 0 && (
            <p className="text-center text-sm text-muted-foreground py-8">No signals generated yet</p>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
