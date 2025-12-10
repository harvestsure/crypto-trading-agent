"use client"

import { useState, useEffect } from "react"
import { ProtectedRoute } from "@/components/auth/protected-route"
import { Sidebar } from "@/components/layout/sidebar"
import { Header } from "@/components/layout/header"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { useAppStore } from "@/lib/store"
import {
  ArrowUpCircle,
  ArrowDownCircle,
  MinusCircle,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Bot,
  Search,
  Filter,
} from "lucide-react"

interface ActivityEvent {
  id: string
  timestamp: Date
  type: "signal" | "order" | "error" | "status"
  agentId: string
  agentName: string
  title: string
  description: string
  metadata?: {
    action?: "buy" | "sell" | "hold"
    symbol?: string
    price?: number
    amount?: number
    status?: "success" | "error" | "pending"
  }
}

export default function ActivityPage() {
  const { agents } = useAppStore()
  const [activities, setActivities] = useState<ActivityEvent[]>([])
  const [filter, setFilter] = useState<string>("all")
  const [searchQuery, setSearchQuery] = useState("")

  useEffect(() => {
    // Generate mock activity data
    const mockActivities: ActivityEvent[] = [
      {
        id: "1",
        timestamp: new Date(Date.now() - 60000),
        type: "signal",
        agentId: "agent-1",
        agentName: "BTC Scalper",
        title: "Buy Signal Generated",
        description: "RSI oversold (28.5), ADX showing strong trend (32.1)",
        metadata: { action: "buy", symbol: "BTC/USDT", price: 43250 },
      },
      {
        id: "2",
        timestamp: new Date(Date.now() - 180000),
        type: "order",
        agentId: "agent-1",
        agentName: "BTC Scalper",
        title: "Order Filled",
        description: "Market buy order executed successfully",
        metadata: { action: "buy", symbol: "BTC/USDT", price: 43245, amount: 0.1, status: "success" },
      },
      {
        id: "3",
        timestamp: new Date(Date.now() - 300000),
        type: "status",
        agentId: "agent-2",
        agentName: "ETH Swing Trader",
        title: "Agent Started",
        description: "Trading agent is now running and monitoring the market",
        metadata: { status: "success" },
      },
      {
        id: "4",
        timestamp: new Date(Date.now() - 600000),
        type: "error",
        agentId: "agent-1",
        agentName: "BTC Scalper",
        title: "API Rate Limit",
        description: "Exchange API rate limit exceeded, retrying in 30 seconds",
        metadata: { status: "error" },
      },
      {
        id: "5",
        timestamp: new Date(Date.now() - 900000),
        type: "signal",
        agentId: "agent-2",
        agentName: "ETH Swing Trader",
        title: "Hold Signal",
        description: "Market consolidating, CHOP index at 58.3",
        metadata: { action: "hold", symbol: "ETH/USDT", price: 2280 },
      },
      {
        id: "6",
        timestamp: new Date(Date.now() - 1200000),
        type: "order",
        agentId: "agent-2",
        agentName: "ETH Swing Trader",
        title: "Take Profit Hit",
        description: "Position closed at target price",
        metadata: { action: "sell", symbol: "ETH/USDT", price: 2350, amount: 0.5, status: "success" },
      },
      {
        id: "7",
        timestamp: new Date(Date.now() - 1800000),
        type: "signal",
        agentId: "agent-1",
        agentName: "BTC Scalper",
        title: "Sell Signal Generated",
        description: "RSI overbought (72.1), bearish divergence detected",
        metadata: { action: "sell", symbol: "BTC/USDT", price: 43800 },
      },
      {
        id: "8",
        timestamp: new Date(Date.now() - 2400000),
        type: "status",
        agentId: "agent-3",
        agentName: "SOL DCA Bot",
        title: "Agent Paused",
        description: "Trading agent paused by user",
        metadata: { status: "pending" },
      },
    ]

    setActivities(mockActivities)
  }, [])

  const getEventIcon = (event: ActivityEvent) => {
    switch (event.type) {
      case "signal":
        if (event.metadata?.action === "buy") return <ArrowUpCircle className="h-5 w-5 text-success" />
        if (event.metadata?.action === "sell") return <ArrowDownCircle className="h-5 w-5 text-destructive" />
        return <MinusCircle className="h-5 w-5 text-muted-foreground" />
      case "order":
        if (event.metadata?.status === "success") return <CheckCircle className="h-5 w-5 text-success" />
        if (event.metadata?.status === "error") return <XCircle className="h-5 w-5 text-destructive" />
        return <CheckCircle className="h-5 w-5 text-warning" />
      case "error":
        return <AlertTriangle className="h-5 w-5 text-destructive" />
      case "status":
        return <Bot className="h-5 w-5 text-primary" />
      default:
        return <Bot className="h-5 w-5 text-muted-foreground" />
    }
  }

  const filteredActivities = activities.filter((activity) => {
    if (filter !== "all" && activity.type !== filter) return false
    if (
      searchQuery &&
      !activity.title.toLowerCase().includes(searchQuery.toLowerCase()) &&
      !activity.description.toLowerCase().includes(searchQuery.toLowerCase()) &&
      !activity.agentName.toLowerCase().includes(searchQuery.toLowerCase())
    ) {
      return false
    }
    return true
  })

  const formatTime = (date: Date) => {
    const diff = Date.now() - date.getTime()
    if (diff < 60000) return "Just now"
    if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`
    if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`
    return date.toLocaleDateString()
  }

  return (
    <ProtectedRoute>
      <div className="flex min-h-screen">
        <Sidebar />
        <main className="flex-1 pl-64">
          <Header title="Activity" description="Real-time activity log from all trading agents" />

          <div className="p-6">
            {/* Filters */}
            <div className="mb-6 flex flex-wrap items-center gap-4">
              <div className="relative flex-1 max-w-sm">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  placeholder="Search activities..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-9"
                />
              </div>
              <Select value={filter} onValueChange={setFilter}>
                <SelectTrigger className="w-40">
                  <Filter className="mr-2 h-4 w-4" />
                  <SelectValue placeholder="Filter" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Events</SelectItem>
                  <SelectItem value="signal">Signals</SelectItem>
                  <SelectItem value="order">Orders</SelectItem>
                  <SelectItem value="error">Errors</SelectItem>
                  <SelectItem value="status">Status</SelectItem>
                </SelectContent>
              </Select>
              <Button
                variant="outline"
                onClick={() => {
                  setFilter("all")
                  setSearchQuery("")
                }}
              >
                Clear Filters
              </Button>
            </div>

            {/* Activity Stats */}
            <div className="mb-6 grid gap-4 md:grid-cols-4">
              <Card>
                <CardContent className="p-4">
                  <div className="text-2xl font-bold text-foreground">
                    {activities.filter((a) => a.type === "signal").length}
                  </div>
                  <p className="text-sm text-muted-foreground">Signals Today</p>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="p-4">
                  <div className="text-2xl font-bold text-success">
                    {activities.filter((a) => a.type === "order" && a.metadata?.status === "success").length}
                  </div>
                  <p className="text-sm text-muted-foreground">Orders Filled</p>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="p-4">
                  <div className="text-2xl font-bold text-destructive">
                    {activities.filter((a) => a.type === "error").length}
                  </div>
                  <p className="text-sm text-muted-foreground">Errors</p>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="p-4">
                  <div className="text-2xl font-bold text-primary">
                    {agents.filter((a) => a.status === "running").length}
                  </div>
                  <p className="text-sm text-muted-foreground">Active Agents</p>
                </CardContent>
              </Card>
            </div>

            {/* Activity List */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Recent Activity</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {filteredActivities.map((activity) => (
                    <div
                      key={activity.id}
                      className="flex gap-4 rounded-lg border border-border p-4 transition-colors hover:bg-secondary/30"
                    >
                      <div className="flex-shrink-0 pt-0.5">{getEventIcon(activity)}</div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-start justify-between gap-4">
                          <div>
                            <p className="font-medium text-foreground">{activity.title}</p>
                            <p className="text-sm text-muted-foreground">{activity.description}</p>
                          </div>
                          <span className="flex-shrink-0 text-xs text-muted-foreground">
                            {formatTime(activity.timestamp)}
                          </span>
                        </div>
                        <div className="mt-2 flex flex-wrap items-center gap-2">
                          <Badge variant="outline" className="text-xs">
                            {activity.agentName}
                          </Badge>
                          {activity.metadata?.symbol && (
                            <Badge variant="secondary" className="text-xs">
                              {activity.metadata.symbol}
                            </Badge>
                          )}
                          {activity.metadata?.price && (
                            <span className="text-xs text-muted-foreground">
                              @ ${activity.metadata.price.toLocaleString()}
                            </span>
                          )}
                          {activity.metadata?.amount && (
                            <span className="text-xs text-muted-foreground">Amount: {activity.metadata.amount}</span>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}

                  {filteredActivities.length === 0 && (
                    <div className="py-12 text-center">
                      <Bot className="mx-auto h-12 w-12 text-muted-foreground" />
                      <p className="mt-4 text-muted-foreground">No activities found</p>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          </div>
        </main>
      </div>
    </ProtectedRoute>
  )
}
