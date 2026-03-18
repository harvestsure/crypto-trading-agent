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
  Activity,
  Zap,
  RefreshCw,
  ChevronDown,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { KlineChart } from "@/components/charts/kline-chart"
import { LiveIndicatorPanel } from "@/components/agents/live-indicator-panel"
import { AITradingSummary } from "@/components/agents/ai-trading-summary"
import { ProfitChart } from "@/components/charts/profit-chart"
import { OrdersTable } from "@/components/agents/orders-table"
import { PositionPanel } from "@/components/agents/position-panel"
import { AgentConversationViewer } from "@/components/agents/agent-conversation-viewer"
import { AgentLogs } from "@/components/agents/agent-logs"
import { EditAgentModal } from "@/components/modals/edit-agent-modal"
import { useAITrading } from "@/hooks/use-ai-trading"
import { useKlineData } from "@/hooks/use-kline-data"
import type { TradingAction } from "@/components/agents/action-history"
import {
  useBackendStatus,
  useOpenPositions,
  useAgentBalance,
  useAgentProfitHistory,
  useTicker,
  useAgentSignals,
} from "@/hooks/use-agent-data"
import { startAgent, stopAgent, triggerAnalysis, getAgent } from "@/lib/api"
import type { Position, AccountBalance, ProfitDataPoint } from "@/lib/types"

const TIMEFRAMES = ["1m", "5m", "15m", "1h", "4h", "1d"]

interface AgentDetailClientProps {
  id: string
}

// Normalize agent data from API or store
function normalizeAgent(data: any) {
  if (!data) return null
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

  // Sync apiAgent to store if agent was fetched from API
  useEffect(() => {
    if (apiAgent && !storeAgent) {
      useAppStore.setState((state) => ({
        agents: [...state.agents, apiAgent],
      }))
    }
  }, [apiAgent, storeAgent, id])

  const model = models.find((m) => m.id === agent?.modelId)
  const exchange = exchanges.find((e) => e.id === agent?.exchangeId)

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
    if (agent?.symbols && agent.symbols.length > 0) {
      setSelectedSymbol((s) => (s ? s : agent.symbols?.[0] ?? ""))
    }
  }, [agent?.symbols])

  useEffect(() => {
    if (agent && agent.timeframe && agent.timeframe !== selectedTimeframe) {
      setSelectedTimeframe(agent.timeframe)
    }
  }, [agent?.timeframe])

  // Real data hooks
  const { positions: openPositions } = useOpenPositions(id, backendConnected && !!agent)
  const { balance: realBalance } = useAgentBalance(id, backendConnected && !!agent)
  const { profitHistory: realProfitHistory } = useAgentProfitHistory(id, 30, backendConnected && !!agent)
  const { ticker } = useTicker(id, selectedSymbol ?? agent?.symbols?.[0] ?? "", backendConnected && !!agent)
  const { signals: realSignals } = useAgentSignals(id, backendConnected && !!agent)

  // Use real data; fall back gracefully to empty states when offline
  const positions = openPositions
  const balance = realBalance ?? {
    totalBalance: 0,
    availableBalance: 0,
    usedMargin: 0,
    unrealizedPnl: 0,
    realizedPnl: 0,
    todayPnl: 0,
    weekPnl: 0,
    monthPnl: 0,
  } as AccountBalance
  const profitData = realProfitHistory

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

  // AI Trading hook (for indicators only)
  const aiTrading = useAITrading({
    symbol: selectedSymbol ?? "",
    timeframe: selectedTimeframe ?? "1h",
    customPrompt: agent?.prompt,
    riskTolerance: "medium",
    autoAnalyze: false,
  })

  // Calculate real-time indicators
  const liveIndicators = liveKlines.length > 50 ? aiTrading.calculateIndicators(liveKlines) : undefined

  // Convert real signals to TradingAction format for AITradingSummary
  const tradingActions: TradingAction[] = realSignals.map((sig: any) => ({
    id: String(sig.id),
    timestamp: sig.timestamp ? new Date(sig.timestamp) : new Date(),
    action: sig.action as any,
    symbol: (sig.indicators_snapshot?.symbol as string) ?? selectedSymbol ?? "",
    confidence: sig.confidence ?? 0.5,
    reasoning: sig.reason ?? "",
    price: (sig.indicators_snapshot?.price as number) ?? undefined,
    positionSize: (sig.indicators_snapshot?.amount as number) ?? undefined,
    stopLoss: sig.stop_loss ?? undefined,
    takeProfit: sig.take_profit ?? undefined,
    result: { status: "executed" as const },
  }))

  // Update price from ticker
  useEffect(() => {
    if (!ticker) return
    const last = Number(ticker.last ?? ticker.close ?? (ticker.info && (ticker.info.lastPrice || ticker.info.last_price)) ?? NaN)
    if (!Number.isFinite(last)) return
    const prev = currentPrice
    let pct: number | null = null
    if (ticker.percentage != null) {
      pct = Number(ticker.percentage)
    } else if (ticker.change != null) {
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
        if (base && base !== 0) {
          const change = ((next - base) / base) * 100
          setPriceChange(Math.round(change * 100) / 100)
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

    useAppStore.setState((state) => ({
      agents: state.agents.map((a) =>
        a.id === agent.id ? { ...a, status: newStatus } : a
      ),
    }))

    if (backendConnected) {
      try {
        if (isRunning) {
          const result = await stopAgent(agent.id)
          if (result.error) {
            useAppStore.setState((state) => ({
              agents: state.agents.map((a) =>
                a.id === agent.id ? { ...a, status: "running" } : a
              ),
            }))
          }
        } else {
          const result = await startAgent(agent.id)
          if (result.error) {
            useAppStore.setState((state) => ({
              agents: state.agents.map((a) =>
                a.id === agent.id ? { ...a, status: "paused" } : a
              ),
            }))
          }
        }
      } catch (error) {
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
      await triggerAnalysis(agent.id)
    } catch (error) {
      // silent
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
      <div className="flex flex-row items-center justify-between gap-3 mb-2 py-2 border-b">
        <div className="px-6">
          <div className="flex items-center gap-3 mb-1">
            <h1 className="text-2xl font-bold font-sans">{agent.name}</h1>
          </div>
          <p className="text-muted-foreground text-sm">{(agent.symbols ?? []).join(", ")} · {agent.timeframe}</p>
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
              onClick={handleTriggerAnalysis}
              disabled={isAnalyzing || !backendConnected}
            >
              {isAnalyzing ? (
                <RefreshCw className="mr-1 h-3 w-3 animate-spin" />
              ) : (
                <Zap className="mr-1 h-3 w-3" />
              )}
              Trigger
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

      {/* Main Content Area — fills remaining height, right panel is fixed, left scrolls */}
      <div className="flex-1 min-h-0 flex gap-3 p-4 overflow-hidden">

        {/* Left Panel: Chart + Stats + Orders (2/3 width) — scrolls independently */}
        <div className="flex flex-col gap-3 flex-2 min-w-0 min-h-0">

          {/* Top row: Chart + Balance */}
          <div className="grid grid-cols-3 gap-3 shrink-0" style={{ height: "340px" }}>
            {/* Chart */}
            <Card className="col-span-2 flex flex-col overflow-hidden h-full">
              <CardHeader className="pb-2 shrink-0">
                <div className="flex items-center justify-between gap-2">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <CardTitle className="text-sm truncate">{selectedSymbol}</CardTitle>
                      <p className="text-sm font-bold text-foreground">
                        {currentPrice != null ? `$${currentPrice.toLocaleString(undefined, { maximumFractionDigits: 2 })}` : "—"}
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
              <CardContent className="flex-1 overflow-hidden p-2">
                <KlineChart
                  agentId={id}
                  symbol={selectedSymbol ?? agent.symbols?.[0] ?? ""}
                  timeframe={selectedTimeframe ?? (agent.timeframe ?? "1h")}
                />
              </CardContent>
            </Card>

            {/* Position / Balance */}
            <PositionPanel
              positions={positions}
              balance={balance}
              agentId={agent.id}
              pnl={pnl}
              totalTrades={totalTrades}
              winRate={winRate}
              lastSignal={lastSignal}
              isProfitable={isProfitable}
            />
          </div>

          {/* Second row: Profit Chart + AI Summary */}
          <div className="grid grid-cols-3 gap-1">
            <div className="col-span-2">
              <ProfitChart data={profitData} title="Profit Curve" />
            </div>
            <div>
              <AITradingSummary actions={tradingActions} currentPositions={positions.length} />
            </div>
          </div>

          {/* Orders Table */}
          <OrdersTable agentId={agent.id} />

          {/* Details Drawer Trigger */}
          <Button
            onClick={() => setShowDetailDrawer(true)}
            className="w-full shrink-0"
            variant="outline"
          >
            <ChevronDown className="mr-2 h-4 w-4" />
            Technical Indicators &amp; Logs
          </Button>
        </div>

        {/* Right Panel: Full-height LLM Conversation — does NOT scroll, card scrolls internally */}
        <div className="h-full min-h-0 overflow-hidden flex flex-col" style={{ minWidth: "300px", maxWidth: "400px", flex: "1" }}>
          <AgentConversationViewer agentId={id} />
        </div>
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
