"use client"

import { useState, useEffect, useRef } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"

interface LogEntry {
  id: string
  timestamp: Date
  level: "info" | "warning" | "error" | "success"
  message: string
}

interface AgentLogsProps {
  agentId: string
}

export function AgentLogs({ agentId }: AgentLogsProps) {
  const [logs, setLogs] = useState<LogEntry[]>([])
  const logsEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    // Generate initial logs
    const initialLogs: LogEntry[] = [
      {
        id: "1",
        timestamp: new Date(Date.now() - 60000),
        level: "info",
        message: "Agent started, connecting to exchange...",
      },
      {
        id: "2",
        timestamp: new Date(Date.now() - 55000),
        level: "success",
        message: "Connected to Binance WebSocket",
      },
      {
        id: "3",
        timestamp: new Date(Date.now() - 50000),
        level: "info",
        message: "Subscribed to BTC/USDT kline stream (1h)",
      },
      {
        id: "4",
        timestamp: new Date(Date.now() - 45000),
        level: "info",
        message: "Calculating indicators: RSI, ADX, CHOP, KAMA",
      },
      {
        id: "5",
        timestamp: new Date(Date.now() - 40000),
        level: "info",
        message: "Sending data to AI model for analysis...",
      },
      {
        id: "6",
        timestamp: new Date(Date.now() - 35000),
        level: "success",
        message: "AI analysis complete: BUY signal generated",
      },
      {
        id: "7",
        timestamp: new Date(Date.now() - 30000),
        level: "info",
        message: "Placing market order: BUY 0.05 BTC @ $42,850",
      },
      {
        id: "8",
        timestamp: new Date(Date.now() - 25000),
        level: "success",
        message: "Order filled successfully",
      },
      {
        id: "9",
        timestamp: new Date(Date.now() - 20000),
        level: "info",
        message: "Setting take profit: $44,000, stop loss: $42,000",
      },
      {
        id: "10",
        timestamp: new Date(Date.now() - 15000),
        level: "warning",
        message: "Rate limit approaching, throttling requests",
      },
    ]

    setLogs(initialLogs)

    // Simulate new logs coming in
    const interval = setInterval(() => {
      const newLog: LogEntry = {
        id: crypto.randomUUID(),
        timestamp: new Date(),
        level: Math.random() > 0.8 ? "warning" : Math.random() > 0.9 ? "error" : "info",
        message: [
          "Received new kline data",
          "Updating indicators...",
          "Market analysis in progress",
          "Monitoring position",
          "Checking stop loss levels",
          "WebSocket heartbeat received",
        ][Math.floor(Math.random() * 6)],
      }

      setLogs((prev) => [...prev.slice(-50), newLog])
    }, 5000)

    return () => clearInterval(interval)
  }, [agentId])

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [logs])

  const getLevelColor = (level: LogEntry["level"]) => {
    switch (level) {
      case "info":
        return "text-primary"
      case "success":
        return "text-success"
      case "warning":
        return "text-warning"
      case "error":
        return "text-destructive"
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Agent Logs</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="h-[400px] overflow-y-auto rounded-lg bg-secondary/50 p-4 font-mono text-xs">
          {logs.map((log) => (
            <div key={log.id} className="flex gap-3 py-1">
              <span className="text-muted-foreground flex-shrink-0">{log.timestamp.toLocaleTimeString()}</span>
              <Badge variant="outline" className={cn("h-5 px-1.5 text-[10px] flex-shrink-0", getLevelColor(log.level))}>
                {log.level.toUpperCase()}
              </Badge>
              <span className="text-foreground">{log.message}</span>
            </div>
          ))}
          <div ref={logsEndRef} />
        </div>
      </CardContent>
    </Card>
  )
}
