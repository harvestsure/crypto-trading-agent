"use client"


import { useState, useEffect, useCallback } from "react"
import { useRouter } from "next/navigation"
import useSWR from "swr"
import { useAppStore } from "@/lib/store"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Drawer, DrawerContent, DrawerHeader, DrawerTitle } from "@/components/ui/drawer"
import {
  ArrowLeft,
  Play,
  Pause,
  Settings,
  TrendingUp,
  TrendingDown,
  Activity,
  Zap,
  RefreshCw,
  ChevronDown,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { KlineChart } from "@/components/charts/kline-chart"
import { IndicatorPanel } from "@/components/agents/indicator-panel"
import { LiveIndicatorPanel } from "@/components/agents/live-indicator-panel"
import { AITradingSummary } from "@/components/agents/ai-trading-summary"
import { ProfitChart } from "@/components/charts/profit-chart"
import { OrdersTable } from "@/components/agents/orders-table"
import { PositionPanel } from "@/components/agents/position-panel"
import { TradingTimeline } from "@/components/agents/trading-timeline"
import type { TimelineEvent } from "@/components/agents/trading-timeline"
import { AgentLogs } from "@/components/agents/agent-logs"
import { EditAgentModal } from "@/components/modals/edit-agent-modal"
import { useAITrading } from "@/hooks/use-ai-trading"
import { useKlineData } from "@/hooks/use-kline-data"
import { calculateAllIndicators } from "@/lib/indicators"
import { generateMockTradingActions } from "@/lib/mock-trading-data"
import type { TradingAction } from "@/components/agents/action-history"
import {
  useBackendStatus,
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
  const [selectedSymbol, setSelectedSymbol] = useState<string>(agent?.symbols?.[0] ?? "")

  useEffect(() => {
    // Default to the first symbol when agent loads or symbols change
    if (agent?.symbols && agent.symbols.length > 0) {
      setSelectedSymbol((s) => (s ? s : agent.symbols?.[0] ?? ""))
    }
  }, [agent?.symbols])

  useEffect(() => {
    // Sync selected timeframe when agent loads or changes
    if (agent && agent.timeframe && agent.timeframe !== selectedTimeframe) {
      setSelectedTimeframe(agent.timeframe)
    }
  }, [agent?.timeframe])

  // Real data hooks - only fetch when backend is connected
  const { positions: openPositions } = useOpenPositions(id, backendConnected && !!agent)
  const { balance: realBalance } = useAgentBalance(id, backendConnected && !!agent)
  const { conversations: realConversations } = useAgentConversations(id, backendConnected && !!agent)
  const { toolCalls: realToolCalls } = useAgentToolCalls(id, backendConnected && !!agent)
  const { profitHistory: realProfitHistory } = useAgentProfitHistory(id, 30, backendConnected && !!agent)
  const { ticker } = useTicker(id, selectedSymbol ?? agent?.symbols?.[0] ?? "", backendConnected && !!agent)

  // Use real data when available, otherwise use mock data
  const positions = (openPositions.length > 0 ? openPositions : [])
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
  const [showDetailDrawer, setShowDetailDrawer] = useState(false)
  const [detailTab, setDetailTab] = useState("indicators")

  // Kline data hook
  const {
    klines: liveKlines,
    isLoading: isLoadingKlines,
    isLive: isKlineLive,
  } = useKlineData({
    exchangeId: agent?.exchangeId ?? "",
    symbol: selectedSymbol ?? "",
    timeframe: selectedTimeframe ?? "1h",
    autoSubscribe: !!agent && backendConnected,
  })

  // AI Trading hook
  const aiTrading = useAITrading({
    symbol: selectedSymbol ?? "",
    timeframe: selectedTimeframe ?? "1h",
    customPrompt: agent?.prompt,
    riskTolerance: "medium",
    autoAnalyze: false, // Manual trigger only
  })

  // Calculate real-time indicators
  const liveIndicators = liveKlines.length > 50 ? aiTrading.calculateIndicators(liveKlines) : undefined

  // Trading actions history
  const [tradingActions, setTradingActions] = useState<TradingAction[]>(() => {
    // Initialize with some mock data for demonstration
    return generateMockTradingActions(12, selectedSymbol ?? agent?.symbols?.[0])
  })

  // Convert trading actions to timeline events
  const timelineEvents: TimelineEvent[] = tradingActions.map((action) => ({
    id: action.id,
    timestamp: action.timestamp,
    type: "execution" as const,
    action: action.action.toLowerCase().replace(/_/g, "_") as any,
    reason: action.reasoning,
    confidence: action.confidence,
    price: action.price,
    takeProfit: action.takeProfit,
    stopLoss: action.stopLoss,
    executionStatus: action.result?.status,
    pnl: action.result?.pnl,
    pnlPercent: action.result?.pnlPercent,
    positionSize: action.positionSize,
    symbol: action.symbol,
  }))

  // Handle AI analysis trigger
  const handleAIAnalysis = useCallback(async () => {
    if (liveKlines.length < 50) {
      console.log("[v0] Insufficient kline data for analysis")
      return
    }

    const result = await aiTrading.analyze(liveKlines)
    if (result) {
      // Add to action history
      const newAction: TradingAction = {
        id: `action_${Date.now()}`,
        timestamp: result.timestamp,
        action: result.decision.action,
        symbol: selectedSymbol ?? "",
        confidence: result.decision.confidence,
        reasoning: result.decision.reasoning,
        price: currentPrice ?? undefined,
        positionSize: result.decision.positionSize,
        stopLoss: result.decision.stopLoss,
        takeProfit: result.decision.takeProfit,
        result: {
          status: "pending",
        },
      }

      setTradingActions((prev) => [newAction, ...prev])
    }
  }, [liveKlines, aiTrading, selectedSymbol, currentPrice])

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
        <div className="flex flex-col items-center justify-center p-12">
          <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
          <p className="mt-4 text-muted-foreground">Loading agent details...</p>
        </div>
      )
    }

    return (
      <div className="flex flex-col items-center justify-center p-12">
        <p className="text-muted-foreground">The agent you are looking for does not exist.</p>
        <Button className="mt-4" onClick={() => router.push("/agents")}>
          Back to Agents
        </Button>
      </div>
    )
  }

  const isRunning = agent.status === "running"
  const pnl = pnlFromPerf ?? 0
  const isProfitable = pnl >= 0

  return (
    <div className="flex flex-col h-full">
      {/* Page Header */}
      <div className="flex flex-row items-center justify-between gap-3 mb-2  py-2 border-b">
        <div className="px-6">
          <div className="flex items-center gap-3 mb-2">
            <h1 className="text-2xl font-bold">{agent.name}</h1>
          </div>
          <p className="text-muted-foreground">{(agent.symbols ?? []).join(", ")} · {agent.timeframe}</p>
        </div>

        {/* Top Control Bar */}
        <div className="flex items-center justify-between gap-3 flex-wrap shrink-0 bg-background p-3 px-6">
          <div className="flex items-center gap-2">
            <Badge variant={backendConnected ? "default" : "secondary"} className="text-xs">
              {backendConnected ? "Live" : "Demo"}
            </Badge>
            <Badge
              variant={isRunning ? "default" : "secondary"}
              className={cn(isRunning && "bg-success text-success-foreground")}
            >
              {isRunning ? "Running" : agent.status}
            </Badge>
          </div>

          <div className="flex items-center gap-2">
            {agent?.symbols && agent.symbols.length > 0 && (
              <Select value={selectedSymbol} onValueChange={(v) => setSelectedSymbol(v)}>
                <SelectTrigger size="sm" className="w-40">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {agent.symbols.map((s: string) => (
                    <SelectItem key={s} value={s}>
                      {s}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
            <Button
              variant="outline"
              size="sm"
              onClick={handleAIAnalysis}
              disabled={aiTrading.isAnalyzing || liveKlines.length < 50}
            >
              {aiTrading.isAnalyzing ? (
                <RefreshCw className="mr-1 h-3 w-3 animate-spin" />
              ) : (
                <Zap className="mr-1 h-3 w-3" />
              )}
              Analyze
            </Button>
            <Button variant="outline" size="icon" onClick={() => setShowSettings(true)}>
              <Settings className="h-4 w-4" />
            </Button>
            <Button size="sm" onClick={handleToggle}>
              {isRunning ? (
                <>
                  <Pause className="mr-1 h-4 w-4" /> Pause
                </>
              ) : (
                <>
                  <Play className="mr-1 h-4 w-4" /> Start
                </>
              )}
            </Button>
          </div>
        </div>
      </div>

      {/* Scrollable Content Area */}
      <div className="flex-1 overflow-auto flex flex-col p-4 gap-3">


        {/* Main 3-Column Layout */}
        <div className="grid gap-3 grid-cols-3 flex-1 min-h-0">
          {/* Left: Chart + AI Trading Summary */}
          <div className="space-y-3 min-h-0 flex flex-col overflow-hidden">
            <Card className="flex-1 flex flex-col overflow-hidden max-h-96">
              <CardHeader className="pb-2 shrink-0">
                <div className="flex items-center justify-between gap-2">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <CardTitle className="text-sm truncate">{selectedSymbol}</CardTitle>
                      <p className="text-sm font-bold text-foreground">
                        {currentPrice != null ? `$${(currentPrice / 1000).toFixed(1)}K` : "—"}
                      </p>
                      <p className={cn("text-xs", priceChange != null ? (priceChange >= 0 ? "text-success" : "text-destructive") : "text-muted-foreground")}> 
                        {priceChange != null ? (priceChange >= 0 ? "+" : "") : ""}
                        {priceChange != null ? `${priceChange.toFixed(1)}%` : "--"}
                      </p>
                    </div>
                    <CardDescription className="text-xs truncate">
                      {exchange?.name ?? "Exchange"} · {selectedTimeframe}
                    </CardDescription>
                  </div>
                  <div className="flex gap-1 shrink-0">
                    {["1m", "1h", "1d"].map((tf) => (
                      <Button
                        key={tf}
                        variant={selectedTimeframe === tf ? "default" : "ghost"}
                        size="sm"
                        className="h-6 px-1 text-xs"
                        onClick={() => setSelectedTimeframe(tf)}
                      >
                        {tf}
                      </Button>
                    ))}
                  </div>
                </div>
              </CardHeader>
              <CardContent className="flex-1 overflow-hidden">
                <KlineChart
                  agentId={id}
                  symbol={selectedSymbol ?? agent.symbols?.[0] ?? ""}
                  timeframe={selectedTimeframe ?? (agent.timeframe ?? "1h")}
                />
              </CardContent>
            </Card>
            <div className="shrink-0">
              <AITradingSummary actions={tradingActions} currentPositions={positions.length} />
            </div>
          </div>

          {/* Middle: Profit Curve + AI Decision + Position */}
          <div className="space-y-3 min-h-0 flex flex-col">
            {/* Profit Curve */}
            <ProfitChart data={profitData} title="Profit Curve" />

            <div className="flex-1 min-h-0 overflow-hidden">
              <PositionPanel positions={positions} balance={balance} agentId={agent.id} />
            </div>
          </div>

          {/* Right: Timeline 占据三行 */}
          <div className="min-h-0 flex flex-col overflow-auto row-span-3">
            <TradingTimeline events={timelineEvents} />
          </div>

          {/* Orders Table: 跨第一列和第二列下方 */}
          <div className="col-span-2 mt-3">
            <OrdersTable agentId={agent.id} />
          </div>
        </div>

        {/* Details Button */}
        <Button
          onClick={() => setShowDetailDrawer(true)}
          className="w-full shrink-0"
          variant="outline"
        >
          <ChevronDown className="mr-2 h-4 w-4" />
          Additional Details (Technical Indicators, Logs)
        </Button>
      </div>

      <EditAgentModal open={showSettings} onOpenChange={setShowSettings} agent={agent} />

      <Drawer open={showDetailDrawer} onOpenChange={setShowDetailDrawer}>
        <DrawerContent className="max-h-[80vh]">
          <DrawerHeader className="border-b">
            <DrawerTitle>Agent Details</DrawerTitle>
          </DrawerHeader>
          <div className="flex-1 overflow-auto p-4">
            <Tabs value={detailTab} onValueChange={setDetailTab} className="w-full">
              <TabsList className="grid w-full grid-cols-2">
                <TabsTrigger value="indicators">Technical Indicators</TabsTrigger>
                <TabsTrigger value="logs">Logs</TabsTrigger>
              </TabsList>

              <div className="mt-4">
                <TabsContent value="indicators">
                  <LiveIndicatorPanel indicators={liveIndicators} isLive={isKlineLive} symbol={selectedSymbol} />
                </TabsContent>

                <TabsContent value="logs">
                  <AgentLogs agentId={agent.id} />
                </TabsContent>
              </div>
            </Tabs>
          </div>
        </DrawerContent>
      </Drawer>
    </div>
  )
}
