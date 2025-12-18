"use client"

import { useState, useEffect, useCallback } from "react"
import { useRouter } from "next/navigation"
import useSWR from "swr"
import { ProtectedRoute } from "@/components/auth/protected-route"
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
  RefreshCw,
  Zap,
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
import { EditAgentModal } from "@/components/modals/edit-agent-modal"
import {
  useBackendStatus,
  useAgentPositions,
  useOpenPositions,
  useAgentBalance,
  useAgentConversations,
  useAgentToolCalls,
  useAgentProfitHistory,
  useTicker,
} from "@/hooks/use-agent-data"
import { startAgent, stopAgent, triggerAnalysis, getAgent } from "@/lib/api"
import type { Position, AccountBalance, ConversationMessage, ToolCall, ProfitDataPoint } from "@/lib/types"

const TIMEFRAMES = ["1m", "5m", "15m", "1h", "4h", "1d"]

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
      "You are a professional cryptocurrency trading agent. Analyze market conditions using technical indicators.",
    timestamp: new Date(Date.now() - 3600000),
  },
  {
    id: "2",
    role: "assistant",
    content: "Analyzing BTC/USDT. RSI at 45.2 (neutral), ADX at 28.5 (trending), MACD showing bullish crossover.",
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
]

const generateMockProfitData = (): ProfitDataPoint[] => {
  const data: ProfitDataPoint[] = []
  let balance = 50000
  for (let i = 30; i >= 0; i--) {
    balance += (Math.random() - 0.45) * 500
    data.push({
      timestamp: Date.now() - i * 24 * 60 * 60 * 1000,
      balance: Math.round(balance * 100) / 100,
      pnl: Math.round((balance - 50000) * 100) / 100,
      pnlPercent: Math.round(((balance - 50000) / 50000) * 10000) / 100,
    })
  }
  return data
}

interface AgentDetailClientProps {
  id: string
}

// Normalize agent data from API or store
function normalizeAgent(data: any) {
  if (!data) return null
  // Ensure we return a full TradingAgent-shaped object so updates to the store
  // keep types consistent (notably `createdAt` is required on `TradingAgent`).
  const createdAt = data.createdAt ?? data.created_at ? new Date(data.created_at ?? data.createdAt) : new Date()
  const performance = data.performance
    ? {
        totalTrades: data.performance.totalTrades ?? data.performance.total_trades ?? 0,
        winRate: data.performance.winRate ?? data.performance.win_rate ?? 0,
        pnl: data.performance.pnl ?? 0,
      }
    : undefined

  const lastSignal = data.lastSignal ?? data.last_signal
  const normalizedLastSignal = lastSignal
    ? {
        action: lastSignal.action,
        timestamp: lastSignal.timestamp ? new Date(lastSignal.timestamp) : new Date(lastSignal.ts ?? Date.now()),
        reason: lastSignal.reason ?? lastSignal.msg ?? "",
      }
    : undefined

  return {
    id: data.id,
    name: data.name,
    modelId: data.modelId || data.model_id,
    exchangeId: data.exchangeId || data.exchange_id,
    symbols: Array.isArray(data.symbols)
      ? data.symbols
      : data.symbol
      ? [data.symbol]
      : [],
    timeframe: data.timeframe,
    status: data.status ?? "paused",
    indicators: data.indicators || [],
    prompt: data.prompt || "",
    performance,
    lastSignal: normalizedLastSignal,
    createdAt,
  }
}

export default function AgentDetailClient({ id }: AgentDetailClientProps) {
  const router = useRouter()
  const agents = useAppStore((state) => state.agents)
  const models = useAppStore((state) => state.models)
  const exchanges = useAppStore((state) => state.exchanges)

  console.log("[DEBUG] AgentDetailClient render, agents count:", agents.length, "agent id:", id)

  // Try to get agent from store first, then fetch from API
  const storeAgent = agents.find((a) => a.id === id)
  const { data: apiAgent, isLoading: isLoadingApiAgent } = useSWR(
    !storeAgent ? `agent-${id}` : null,
    async () => {
      const result = await getAgent(id)
      if (result.error || !result.data) return null
      return normalizeAgent(result.data)
    },
    { revalidateOnFocus: false },
  )

  const agent = storeAgent ? normalizeAgent(storeAgent) : apiAgent
  console.log("[DEBUG] Current agent status:", agent?.status)

  // Sync apiAgent to store if agent was fetched from API
  useEffect(() => {
    if (apiAgent && !storeAgent) {
      console.log("[DEBUG] Syncing apiAgent to store:", apiAgent)
      useAppStore.setState((state) => ({
        agents: [...state.agents, apiAgent],
      }))
    }
  }, [apiAgent, storeAgent, id])

  const model = models.find((m) => m.id === agent?.modelId)
  const exchange = exchanges.find((e) => e.id === agent?.exchangeId)

  // Normalize/defensive reads for agent fields coming from the store (snake_case vs camelCase)
  const indicators: string[] = ((agent as any)?.indicators as string[]) ?? []
  const perfRaw = (agent as any)?.performance ?? {}
  const totalTrades: number = (perfRaw?.totalTrades ?? perfRaw?.total_trades ?? 0) as number
  const winRate: number = (perfRaw?.winRate ?? perfRaw?.win_rate ?? 0) as number
  const pnlFromPerf: number = perfRaw?.pnl ?? 0
  const lastSignal = (agent as any)?.lastSignal ?? null

  const { isConnected: backendConnected } = useBackendStatus()

  const [selectedTimeframe, setSelectedTimeframe] = useState<string>(agent?.timeframe ?? "1h")

  useEffect(() => {
    // Sync selected timeframe when agent loads or changes
    if (agent && agent.timeframe && agent.timeframe !== selectedTimeframe) {
      setSelectedTimeframe(agent.timeframe)
    }
  }, [agent?.timeframe])

  // Real data hooks - only fetch when backend is connected
  const { positions: realPositions } = useAgentPositions(id, backendConnected && !!agent)
  const { positions: openPositions } = useOpenPositions(id, backendConnected && !!agent)
  const { balance: realBalance } = useAgentBalance(id, backendConnected && !!agent)
  const { conversations: realConversations } = useAgentConversations(id, backendConnected && !!agent)
  const { toolCalls: realToolCalls } = useAgentToolCalls(id, backendConnected && !!agent)
  const { profitHistory: realProfitHistory } = useAgentProfitHistory(id, 30, backendConnected && !!agent)
  const { ticker } = useTicker(id, agent?.symbols?.[0] ?? "", backendConnected && !!agent)

  // Use real data when available, otherwise use mock data
  // Prioritize openPositions (new endpoint), then fall back to realPositions, then mockPositions
  const positions = openPositions.length > 0 ? openPositions : (realPositions.length > 0 ? realPositions : mockPositions)
  const balance = realBalance ? realBalance : mockBalance
  const conversations = realConversations.length > 0 ? realConversations : mockConversations
  const toolCalls = realToolCalls.length > 0 ? realToolCalls : mockToolCalls
  const [mockProfitData] = useState<ProfitDataPoint[]>(generateMockProfitData())
  const profitData = realProfitHistory.length > 0 ? realProfitHistory : mockProfitData

  // Price state
  const [currentPrice, setCurrentPrice] = useState<number | null>(null)
  const [priceChange, setPriceChange] = useState<number | null>(null)
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [showSettings, setShowSettings] = useState(false)

  // Update price from ticker
  useEffect(() => {
    if (!ticker) return

    // Normalize last price
    const last = Number(ticker.last ?? ticker.close ?? (ticker.info && (ticker.info.lastPrice || ticker.info.last_price)) ?? NaN)
    if (!Number.isFinite(last)) return

    const prev = currentPrice
    // Prefer percentage field from ticker if available (ccxt uses 'percentage')
    let pct: number | null = null
    if (ticker.percentage != null) {
      pct = Number(ticker.percentage)
    } else if (ticker.change != null) {
      // 'change' can be absolute price change; convert to percent if we have a previous price
      const changeVal = Number(ticker.change)
      if (Number.isFinite(changeVal) && prev && prev !== 0) {
        pct = (changeVal / prev) * 100
      }
    } else if (prev && prev !== 0) {
      pct = ((last - prev) / prev) * 100
    }

    setCurrentPrice(last)
    setPriceChange(Number.isFinite(pct ?? NaN) ? Math.round((pct as number) * 100) / 100 : null)
  }, [ticker])

  // Simulate price updates when not connected
  useEffect(() => {
    if (backendConnected) return
    const interval = setInterval(() => {
      setCurrentPrice((prev) => {
        const base = prev ?? 43250.5
        const next = Math.round((base + (Math.random() - 0.5) * 100) * 100) / 100
        // compute percent change relative to base price
        if (base && base !== 0) {
          const change = ((next - base) / base) * 100
          setPriceChange(Math.round(change * 100) / 100)
        } else {
          setPriceChange(null)
        }
        return next
      })
    }, 3000)
    return () => clearInterval(interval)
  }, [backendConnected])

  const handleToggle = useCallback(async () => {
    if (!agent) return

    const isRunning = agent.status === "running"
    const newStatus = isRunning ? "paused" : "running"

    console.log("[DEBUG] handleToggle called, isRunning:", isRunning, "newStatus:", newStatus)

    // Update store immediately for responsiveness
    useAppStore.setState((state) => ({
      agents: state.agents.map((a) =>
        a.id === agent.id ? { ...a, status: newStatus } : a
      ),
    }))
    
    console.log("[DEBUG] Store updated, new agents:", useAppStore.getState().agents)

    // Call API to actually start/stop the agent
    if (backendConnected) {
      try {
        if (isRunning) {
          const result = await stopAgent(agent.id)
          if (result.error) {
            console.error("[v0] Failed to stop agent:", result.error)
            // Revert on error
            useAppStore.setState((state) => ({
              agents: state.agents.map((a) =>
                a.id === agent.id ? { ...a, status: "running" } : a
              ),
            }))
          }
        } else {
          const result = await startAgent(agent.id)
          if (result.error) {
            console.error("[v0] Failed to start agent:", result.error)
            // Revert on error
            useAppStore.setState((state) => ({
              agents: state.agents.map((a) =>
                a.id === agent.id ? { ...a, status: "paused" } : a
              ),
            }))
          }
        }
      } catch (error) {
        console.error("[v0] Failed to toggle agent:", error)
        // Revert on error
        useAppStore.setState((state) => ({
          agents: state.agents.map((a) =>
            a.id === agent.id ? { ...a, status: isRunning ? "running" : "paused" } : a
          ),
        }))
      }
    }
  }, [agent, backendConnected])

  const handleTriggerAnalysis = useCallback(async () => {
    if (!agent || !backendConnected) return

    setIsAnalyzing(true)
    try {
      const result = await triggerAnalysis(agent.id)
      if (result.data) {
        console.log("[v0] Analysis result:", result.data)
      }
    } catch (error) {
      console.error("[v0] Analysis failed:", error)
    } finally {
      setIsAnalyzing(false)
    }
  }, [agent, backendConnected])

  if (!agent) {
    if (isLoadingApiAgent) {
      return (
        <div className="flex min-h-screen">
          <Sidebar />
          <main className="flex-1 pl-64">
            <Header title="Loading..." />
            <div className="flex flex-col items-center justify-center p-12">
              <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
              <p className="mt-4 text-muted-foreground">Loading agent details...</p>
            </div>
          </main>
        </div>
      )
    }

    return (
      <div className="flex min-h-screen">
        <Sidebar />
        <main className="flex-1 pl-64">
          <Header title="Agent Not Found" />
          <div className="flex flex-col items-center justify-center p-12">
            <p className="text-muted-foreground">The agent you are looking for does not exist.</p>
            <Button className="mt-4" onClick={() => router.push("/agents")}>
              Back to Agents
            </Button>
          </div>
        </main>
      </div>
    )
  }

  const isRunning = agent.status === "running"
  const pnl = pnlFromPerf ?? 0
  const isProfitable = pnl >= 0

  return (
    <ProtectedRoute>
      <div className="flex min-h-screen">
        <Sidebar />
        <main className="flex-1 pl-64">
          <Header title={agent.name} description={`${(agent.symbols ?? []).join(", ")} · ${agent.timeframe}`} />

          <div className="p-6">
            {/* Top Navigation & Controls */}
            <div className="mb-6 flex items-center justify-between">
              <div className="flex items-center gap-4">
                <Button variant="ghost" onClick={() => router.push("/agents")}>
                  <ArrowLeft className="mr-2 h-4 w-4" />
                  Back
                </Button>
                <Badge variant={backendConnected ? "default" : "secondary"} className="text-xs">
                  {backendConnected ? "Live Data" : "Demo Mode"}
                </Badge>
              </div>

              <div className="flex items-center gap-3">
                <Badge
                  variant={isRunning ? "default" : "secondary"}
                  className={cn(isRunning && "bg-success text-success-foreground")}
                >
                  {isRunning ? "Running" : agent.status}
                </Badge>
                {backendConnected && (
                  <Button variant="outline" size="sm" onClick={handleTriggerAnalysis} disabled={isAnalyzing}>
                    {isAnalyzing ? (
                      <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                    ) : (
                      <Zap className="mr-2 h-4 w-4" />
                    )}
                    Analyze Now
                  </Button>
                )}
                <Button variant="outline" size="icon" onClick={() => setShowSettings(true)}>
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
                      <p className="text-2xl font-bold text-foreground">
                        {currentPrice != null ? `$${currentPrice.toLocaleString()}` : "—"}
                      </p>
                      <p
                        className={cn(
                          "flex items-center text-sm",
                          priceChange != null ? (priceChange >= 0 ? "text-success" : "text-destructive") : "text-muted-foreground",
                        )}
                      >
                        {priceChange != null ? (
                          priceChange >= 0 ? (
                            <TrendingUp className="mr-1 h-3 w-3" />
                          ) : (
                            <TrendingDown className="mr-1 h-3 w-3" />
                          )
                        ) : null}
                        {priceChange != null ? (priceChange >= 0 ? "+" : "") : ""}
                        {priceChange != null ? `${priceChange.toFixed(2)}%` : "--"}
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
                      <p className="text-2xl font-bold text-foreground">
                        ${(balance?.totalBalance ?? 0).toLocaleString()}
                      </p>
                      <p className="text-sm text-muted-foreground">
                        ${(balance?.availableBalance ?? 0).toLocaleString()} available
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
                      <p className="text-sm text-muted-foreground">{totalTrades} trades</p>
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
                      <p className="text-2xl font-bold text-foreground">{winRate}%</p>
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
                      <p className="text-2xl font-bold text-foreground capitalize">{lastSignal?.action ?? "None"}</p>
                      <p className="text-sm text-muted-foreground">
                        {lastSignal ? new Date((lastSignal as any).timestamp).toLocaleTimeString() : "No signals yet"}
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
                        <CardTitle>{(agent.symbols ?? []).join(", ")}</CardTitle>
                        <CardDescription>
                          {exchange?.name ?? "Exchange"} · {agent.timeframe} timeframe
                        </CardDescription>
                      </div>
                      <div className="flex gap-2">
                        {TIMEFRAMES.map((tf) => (
                          <Button
                            key={tf}
                            variant={selectedTimeframe === tf ? "default" : "ghost"}
                            size="sm"
                            className="h-7 px-2 text-xs"
                            onClick={() => setSelectedTimeframe(tf)}
                          >
                            {tf}
                          </Button>
                        ))}
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <KlineChart agentId={id} symbol={agent.symbols?.[0] ?? ""} timeframe={selectedTimeframe ?? (agent.timeframe ?? "1h")} />
                  </CardContent>
                </Card>
                <ProfitChart data={profitData} title="30-Day Performance" />
              </div>

              {/* Positions & Indicators Panel */}
              <div className="space-y-6">
                <PositionPanel positions={positions} balance={balance} />
                <IndicatorPanel indicators={indicators} />
              </div>

              {/* AI Conversation & Tools */}
              <div className="space-y-6">
                <ConversationHistory messages={conversations} />
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
                  <ToolOperations toolCalls={toolCalls} />
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
                          {indicators.map((ind: string) => (
                            <Badge key={ind} variant="secondary">
                              {ind}
                            </Badge>
                          ))}
                        </div>
                      </div>
                      <div className="rounded-lg border border-border p-4">
                        <p className="text-sm font-medium text-muted-foreground mb-2">System Prompt</p>
                        <pre className="whitespace-pre-wrap rounded bg-secondary p-3 text-xs text-foreground font-mono">
                          {(agent as any).prompt ?? ""}
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

      <EditAgentModal open={showSettings} onOpenChange={setShowSettings} agent={agent} />
    </ProtectedRoute>
  )
}
