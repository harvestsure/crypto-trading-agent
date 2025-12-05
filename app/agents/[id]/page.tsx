"use client"

import { useState, useEffect } from "react"
import { useRouter } from "next/navigation"
import { useAppStore } from "@/lib/store"
import { Sidebar } from "@/components/layout/sidebar"
import { Header } from "@/components/layout/header"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  ArrowLeft,
  Play,
  Pause,
  Settings,
  TrendingUp,
  TrendingDown,
  Activity,
  Clock,
  Target,
  Wallet,
  Wrench,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { KlineChart } from "@/components/charts/kline-chart"
import { ProfitChart } from "@/components/charts/profit-chart"
import { IndicatorPanel } from "@/components/agents/indicator-panel"
import { PositionPanel } from "@/components/agents/position-panel"
import { ConversationHistory } from "@/components/agents/conversation-history"
import { ToolOperations } from "@/components/agents/tool-operations"
import { SignalHistory } from "@/components/agents/signal-history"
import { OrdersTable } from "@/components/agents/orders-table"
import { AgentLogs } from "@/components/agents/agent-logs"
import type { Position, AccountBalance, ConversationMessage, ToolCall, ProfitDataPoint } from "@/lib/types"

interface AgentDetailClientProps {
  id: string
}

// Mock data for demo
const mockPositions: Position[] = [
  {
    symbol: "BTC/USDT",
    side: "long",
    size: 0.5,
    entryPrice: 42850,
    currentPrice: 43250,
    leverage: 10,
    unrealizedPnl: 200,
    unrealizedPnlPercent: 0.93,
    liquidationPrice: 38565,
    margin: 2142.5,
    timestamp: new Date(),
  },
  {
    symbol: "ETH/USDT",
    side: "short",
    size: 5,
    entryPrice: 2680,
    currentPrice: 2650,
    leverage: 5,
    unrealizedPnl: 150,
    unrealizedPnlPercent: 1.12,
    liquidationPrice: 3216,
    margin: 2680,
    timestamp: new Date(),
  },
]

const mockBalance: AccountBalance = {
  totalBalance: 52450.8,
  availableBalance: 47628.3,
  usedMargin: 4822.5,
  unrealizedPnl: 350,
  realizedPnl: 1250.5,
  todayPnl: 2.35,
  weekPnl: 5.82,
  monthPnl: 12.45,
}

const mockConversations: ConversationMessage[] = [
  {
    id: "1",
    role: "system",
    content:
      "You are a professional cryptocurrency trading agent. Analyze market conditions using technical indicators and execute trades accordingly.",
    timestamp: new Date(Date.now() - 3600000),
  },
  {
    id: "2",
    role: "assistant",
    content:
      "Analyzing BTC/USDT market conditions. RSI at 45.2 (neutral), ADX at 28.5 (trending), MACD showing bullish crossover. Market structure suggests potential long opportunity.",
    timestamp: new Date(Date.now() - 3500000),
  },
  {
    id: "3",
    role: "tool",
    content: "Executing long position on BTC/USDT",
    timestamp: new Date(Date.now() - 3400000),
    toolCall: {
      id: "tc1",
      name: "create_order",
      arguments: { symbol: "BTC/USDT", side: "buy", amount: 0.5, leverage: 10 },
      result: "Order filled at $42,850",
      status: "success",
      timestamp: new Date(Date.now() - 3400000),
    },
  },
  {
    id: "4",
    role: "tool",
    content: "Setting stop loss",
    timestamp: new Date(Date.now() - 3300000),
    toolCall: {
      id: "tc2",
      name: "set_stop_loss",
      arguments: { symbol: "BTC/USDT", price: 41500 },
      result: "Stop loss set at $41,500",
      status: "success",
      timestamp: new Date(Date.now() - 3300000),
    },
  },
  {
    id: "5",
    role: "assistant",
    content:
      "Position opened successfully. Entry: $42,850, Stop Loss: $41,500 (-3.15%), Take Profit: $45,000 (+5.01%). Risk/Reward ratio: 1:1.59. Monitoring market conditions for potential adjustments.",
    timestamp: new Date(Date.now() - 3200000),
  },
]

const mockToolCalls: ToolCall[] = [
  {
    id: "tc1",
    name: "get_market_data",
    arguments: { symbol: "BTC/USDT", timeframe: "1h" },
    result: "Fetched 100 candles",
    status: "success",
    timestamp: new Date(Date.now() - 3600000),
  },
  {
    id: "tc2",
    name: "create_order",
    arguments: { symbol: "BTC/USDT", side: "buy", amount: 0.5, leverage: 10 },
    result: "Order filled at $42,850",
    status: "success",
    timestamp: new Date(Date.now() - 3400000),
  },
  {
    id: "tc3",
    name: "set_stop_loss",
    arguments: { symbol: "BTC/USDT", price: 41500 },
    result: "Stop loss set at $41,500",
    status: "success",
    timestamp: new Date(Date.now() - 3300000),
  },
  {
    id: "tc4",
    name: "set_take_profit",
    arguments: { symbol: "BTC/USDT", price: 45000 },
    result: "Take profit set at $45,000",
    status: "success",
    timestamp: new Date(Date.now() - 3200000),
  },
  {
    id: "tc5",
    name: "get_positions",
    arguments: {},
    result: "2 open positions",
    status: "success",
    timestamp: new Date(Date.now() - 1800000),
  },
]

// Generate mock profit data
const generateProfitData = (): ProfitDataPoint[] => {
  const data: ProfitDataPoint[] = []
  const now = Date.now()
  let balance = 50000
  let pnl = 0

  for (let i = 30; i >= 0; i--) {
    const change = (Math.random() - 0.45) * 500
    balance += change
    pnl = ((balance - 50000) / 50000) * 100
    data.push({
      timestamp: now - i * 24 * 60 * 60 * 1000,
      balance: Math.round(balance * 100) / 100,
      pnl: Math.round((balance - 50000) * 100) / 100,
      pnlPercent: Math.round(pnl * 100) / 100,
    })
  }
  return data
}

const AgentDetailClient = ({ id }: AgentDetailClientProps) => {
  const router = useRouter()
  const { agents, models, exchanges, updateAgent } = useAppStore()

  const agent = agents.find((a) => a.id === id)
  const model = models.find((m) => m.id === agent?.modelId)
  const exchange = exchanges.find((e) => e.id === agent?.exchangeId)

  const [currentPrice, setCurrentPrice] = useState(43250.5)
  const [priceChange, setPriceChange] = useState(2.35)
  const [profitData] = useState<ProfitDataPoint[]>(generateProfitData())

  // Simulate price updates
  useEffect(() => {
    const interval = setInterval(() => {
      setCurrentPrice((prev) => {
        const change = (Math.random() - 0.5) * 100
        return Math.round((prev + change) * 100) / 100
      })
      setPriceChange((prev) => {
        const change = (Math.random() - 0.5) * 0.5
        return Math.round((prev + change) * 100) / 100
      })
    }, 3000)
    return () => clearInterval(interval)
  }, [])

  if (!agent) {
    return (
      <div className="flex min-h-screen">
        <Sidebar />
        <main className="flex-1 pl-64">
          <Header title="Agent Not Found" />
          <div className="flex flex-col items-center justify-center p-12">
            <p className="text-muted-foreground">The agent you're looking for doesn't exist.</p>
            <Button className="mt-4" onClick={() => router.push("/agents")}>
              Back to Agents
            </Button>
          </div>
        </main>
      </div>
    )
  }

  const isRunning = agent.status === "running"
  const pnl = agent.performance?.pnl ?? 0
  const isProfitable = pnl >= 0

  const handleToggle = () => {
    updateAgent(agent.id, {
      status: isRunning ? "paused" : "running",
    })
  }

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="flex-1 pl-64">
        <Header title={agent.name} description={`${agent.symbol} · ${agent.timeframe}`} />

        <div className="p-6">
          {/* Top Navigation & Controls */}
          <div className="mb-6 flex items-center justify-between">
            <Button variant="ghost" onClick={() => router.push("/agents")}>
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back to Agents
            </Button>

            <div className="flex items-center gap-3">
              <Badge
                variant={isRunning ? "default" : "secondary"}
                className={cn(isRunning && "bg-success text-success-foreground")}
              >
                {isRunning ? "Running" : agent.status}
              </Badge>
              <Button variant="outline" size="icon">
                <Settings className="h-4 w-4" />
              </Button>
              <Button onClick={handleToggle}>
                {isRunning ? (
                  <>
                    <Pause className="mr-2 h-4 w-4" /> Pause
                  </>
                ) : (
                  <>
                    <Play className="mr-2 h-4 w-4" /> Start
                  </>
                )}
              </Button>
            </div>
          </div>

          {/* Stats Cards */}
          <div className="mb-6 grid gap-4 md:grid-cols-2 lg:grid-cols-5">
            <Card>
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">Current Price</p>
                    <p className="text-2xl font-bold text-foreground">${currentPrice.toLocaleString()}</p>
                    <p
                      className={cn(
                        "flex items-center text-sm",
                        priceChange >= 0 ? "text-success" : "text-destructive",
                      )}
                    >
                      {priceChange >= 0 ? (
                        <TrendingUp className="mr-1 h-3 w-3" />
                      ) : (
                        <TrendingDown className="mr-1 h-3 w-3" />
                      )}
                      {priceChange >= 0 ? "+" : ""}
                      {priceChange}%
                    </p>
                  </div>
                  <Activity className="h-8 w-8 text-primary" />
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">Total Balance</p>
                    <p className="text-2xl font-bold text-foreground">${mockBalance.totalBalance.toLocaleString()}</p>
                    <p className="text-sm text-muted-foreground">
                      ${mockBalance.availableBalance.toLocaleString()} available
                    </p>
                  </div>
                  <Wallet className="h-8 w-8 text-primary" />
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">Total PnL</p>
                    <p className={cn("text-2xl font-bold", isProfitable ? "text-success" : "text-destructive")}>
                      {isProfitable ? "+" : ""}
                      {pnl.toFixed(2)}%
                    </p>
                    <p className="text-sm text-muted-foreground">{agent.performance?.totalTrades ?? 0} trades</p>
                  </div>
                  {isProfitable ? (
                    <TrendingUp className="h-8 w-8 text-success" />
                  ) : (
                    <TrendingDown className="h-8 w-8 text-destructive" />
                  )}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">Win Rate</p>
                    <p className="text-2xl font-bold text-foreground">{agent.performance?.winRate ?? 0}%</p>
                    <p className="text-sm text-muted-foreground">Last 30 days</p>
                  </div>
                  <Target className="h-8 w-8 text-primary" />
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">Last Signal</p>
                    <p className="text-2xl font-bold text-foreground capitalize">
                      {agent.lastSignal?.action ?? "None"}
                    </p>
                    <p className="text-sm text-muted-foreground">
                      {agent.lastSignal ? new Date(agent.lastSignal.timestamp).toLocaleTimeString() : "No signals yet"}
                    </p>
                  </div>
                  <Clock className="h-8 w-8 text-primary" />
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Main Content - 3 Column Layout */}
          <div className="grid gap-6 lg:grid-cols-4">
            {/* Chart Section */}
            <div className="lg:col-span-2 space-y-6">
              <Card>
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between">
                    <div>
                      <CardTitle>{agent.symbol}</CardTitle>
                      <CardDescription>
                        {exchange?.name} · {agent.timeframe} timeframe
                      </CardDescription>
                    </div>
                    <div className="flex gap-2">
                      {["1m", "5m", "15m", "1h", "4h", "1d"].map((tf) => (
                        <Button
                          key={tf}
                          variant={agent.timeframe === tf ? "default" : "ghost"}
                          size="sm"
                          className="h-7 px-2 text-xs"
                        >
                          {tf}
                        </Button>
                      ))}
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  <KlineChart symbol={agent.symbol} timeframe={agent.timeframe} />
                </CardContent>
              </Card>

              {/* Profit Chart */}
              <ProfitChart data={profitData} title="30-Day Performance" />
            </div>

            {/* Positions & Indicators Panel */}
            <div className="space-y-6">
              <PositionPanel positions={mockPositions} balance={mockBalance} />
              <IndicatorPanel indicators={agent.indicators} />
            </div>

            {/* AI Conversation & Tools */}
            <div className="space-y-6">
              <ConversationHistory messages={mockConversations} />
            </div>
          </div>

          {/* Tabs Section */}
          <div className="mt-6">
            <Tabs defaultValue="tools">
              <TabsList>
                <TabsTrigger value="tools" className="flex items-center gap-2">
                  <Wrench className="h-4 w-4" />
                  Tool Operations
                </TabsTrigger>
                <TabsTrigger value="signals">Signals</TabsTrigger>
                <TabsTrigger value="orders">Orders</TabsTrigger>
                <TabsTrigger value="logs">Logs</TabsTrigger>
                <TabsTrigger value="config">Configuration</TabsTrigger>
              </TabsList>

              <TabsContent value="tools" className="mt-4">
                <ToolOperations toolCalls={mockToolCalls} />
              </TabsContent>

              <TabsContent value="signals" className="mt-4">
                <SignalHistory agentId={agent.id} />
              </TabsContent>

              <TabsContent value="orders" className="mt-4">
                <OrdersTable agentId={agent.id} />
              </TabsContent>

              <TabsContent value="logs" className="mt-4">
                <AgentLogs agentId={agent.id} />
              </TabsContent>

              <TabsContent value="config" className="mt-4">
                <Card>
                  <CardHeader>
                    <CardTitle>Agent Configuration</CardTitle>
                    <CardDescription>Current settings for this trading agent</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="grid gap-4 md:grid-cols-2">
                      <div className="rounded-lg border border-border p-4">
                        <p className="text-sm font-medium text-muted-foreground">AI Model</p>
                        <p className="text-foreground">{model?.name ?? "Unknown"}</p>
                        <p className="text-xs text-muted-foreground">{model?.model}</p>
                      </div>
                      <div className="rounded-lg border border-border p-4">
                        <p className="text-sm font-medium text-muted-foreground">Exchange</p>
                        <p className="text-foreground">{exchange?.name ?? "Unknown"}</p>
                        <p className="text-xs text-muted-foreground capitalize">{exchange?.exchange}</p>
                      </div>
                    </div>

                    <div className="rounded-lg border border-border p-4">
                      <p className="text-sm font-medium text-muted-foreground mb-2">Indicators</p>
                      <div className="flex flex-wrap gap-2">
                        {agent.indicators.map((ind) => (
                          <Badge key={ind} variant="secondary">
                            {ind}
                          </Badge>
                        ))}
                      </div>
                    </div>

                    <div className="rounded-lg border border-border p-4">
                      <p className="text-sm font-medium text-muted-foreground mb-2">System Prompt</p>
                      <pre className="whitespace-pre-wrap rounded bg-secondary p-3 text-xs text-foreground font-mono">
                        {agent.prompt}
                      </pre>
                    </div>
                  </CardContent>
                </Card>
              </TabsContent>
            </Tabs>
          </div>
        </div>
      </main>
    </div>
  )
}

interface PageProps {
  params: Promise<{ id: string }>
}

export default async function AgentDetailPage({ params }: PageProps) {
  const { id } = await params

  return <AgentDetailClient id={id} />
}
