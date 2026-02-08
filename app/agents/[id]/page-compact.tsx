"use client"

import { useState, useEffect, useCallback } from "react"
import { useRouter } from "next/navigation"
import useSWR from "swr"
import { ProtectedRoute } from "@/components/auth/protected-route"
import { useAppStore } from "@/lib/store"
import { Sidebar } from "@/components/layout/sidebar"
import { Header } from "@/components/layout/header"
import { useSidebar } from "@/contexts/sidebar-context"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  ArrowLeft,
  Play,
  Pause,
  TrendingUp,
  TrendingDown,
  Activity,
  Zap,
  RefreshCw,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { SimpleKlineChart } from "@/components/charts/simple-kline-chart"
import { startAgent, stopAgent, getAgent } from "@/lib/api"
import { useAITrading } from "@/hooks/use-ai-trading"
import { useKlineData } from "@/hooks/use-kline-data"
import { useTradingActions } from "@/hooks/use-trading-actions"
import { useBackendStatus } from "@/hooks/use-agent-data"
import type { TradingAgent, Position, AccountBalance } from "@/lib/types"
import type { TradingAction } from "@/components/agents/action-history"

interface PageProps {
  params: { id: string }
}

export default function CompactAgentPage({ params }: PageProps) {
  const { id } = params
  const router = useRouter()
  const { isCollapsed } = useSidebar()
  const { backendConnected } = useBackendStatus()

  // Fetch agent data
  const { data: agentResponse, mutate: mutateAgent } = useSWR(`agent-${id}`, () => getAgent(id))
  const agent = agentResponse?.data

  // State
  const [selectedSymbol, setSelectedSymbol] = useState<string>("")
  const [selectedTimeframe, setSelectedTimeframe] = useState<string>("1h")

  // Real-time kline data
  const {
    klines,
    isLoading: isLoadingKlines,
    isLive,
    subscribe,
    unsubscribe,
  } = useKlineData({
    exchangeId: agent?.exchangeId ?? "",
    symbol: selectedSymbol,
    timeframe: selectedTimeframe,
    autoSubscribe: false,
  })

  // AI Trading
  const aiTrading = useAITrading({
    symbol: selectedSymbol,
    timeframe: selectedTimeframe,
    customPrompt: agent?.prompt,
    riskTolerance: "medium",
    autoAnalyze: false,
  })

  // Trading Actions
  const tradingActions = useTradingActions({
    agentId: id,
    limit: 50,
    autoRefresh: true,
  })

  // Calculate real-time indicators and current price
  const indicators = klines.length > 50 ? aiTrading.calculateIndicators(klines) : undefined
  const latestKline = klines[klines.length - 1]
  const currentPrice = latestKline?.close

  // Initialize symbol
  useEffect(() => {
    if (agent?.symbols?.[0] && !selectedSymbol) {
      setSelectedSymbol(agent.symbols[0])
    }
  }, [agent, selectedSymbol])

  // Auto-subscribe to kline data
  useEffect(() => {
    if (agent && selectedSymbol && backendConnected) {
      subscribe()
      return () => unsubscribe()
    }
  }, [agent, selectedSymbol, backendConnected, subscribe, unsubscribe])

  // Handle agent start/stop
  const handleToggleAgent = async () => {
    if (!agent) return

    try {
      if (agent.status === "running") {
        await stopAgent(id)
      } else {
        await startAgent(id)
      }
      mutateAgent()
    } catch (error) {
      console.error("[v0] Toggle agent error:", error)
    }
  }

  // Handle AI analysis
  const handleAIAnalysis = useCallback(async () => {
    if (klines.length < 50) {
      console.log("[v0] Insufficient kline data for analysis")
      return
    }

    const result = await aiTrading.analyze(klines)
    
    // Submit action to backend
    if (result && result.decision.action !== "HOLD") {
      const action: Omit<TradingAction, "id" | "timestamp"> = {
        action: result.decision.action,
        symbol: selectedSymbol,
        confidence: result.decision.confidence,
        reasoning: result.decision.reasoning,
        price: currentPrice,
        positionSize: result.decision.positionSize,
        stopLoss: result.decision.stopLoss,
        takeProfit: result.decision.takeProfit,
        result: {
          status: "pending",
        },
      }

      await tradingActions.submitAction(action)
    }
  }, [klines, aiTrading, tradingActions, selectedSymbol, currentPrice])

  if (!agent) {
    return (
      <ProtectedRoute>
        <div className="flex h-screen items-center justify-center">
          <div className="text-center">
            <RefreshCw className="mx-auto h-8 w-8 animate-spin text-muted-foreground" />
            <p className="mt-2 text-sm text-muted-foreground">Loading agent...</p>
          </div>
        </div>
      </ProtectedRoute>
    )
  }

  return (
    <ProtectedRoute>
      <div className="flex h-screen overflow-hidden">
        <Sidebar />
        <div className="flex flex-1 flex-col overflow-hidden">
          <Header />
          <main
            className={cn(
              "flex-1 overflow-hidden bg-background p-4 transition-all duration-300",
              isCollapsed ? "ml-16" : "ml-64"
            )}
          >
            {/* Fixed height container - no scrolling */}
            <div className="flex h-full flex-col gap-4">
              {/* Top Bar */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <Button variant="ghost" size="icon" onClick={() => router.push("/agents")}>
                    <ArrowLeft className="h-4 w-4" />
                  </Button>
                  <div>
                    <h1 className="text-2xl font-bold">{agent.name}</h1>
                    <p className="text-sm text-muted-foreground">
                      {selectedSymbol} · {selectedTimeframe}
                    </p>
                  </div>
                  <Badge variant={agent.status === "running" ? "default" : "secondary"}>
                    {agent.status}
                  </Badge>
                </div>

                <div className="flex items-center gap-2">
                  <Button variant="outline" size="sm" onClick={handleToggleAgent}>
                    {agent.status === "running" ? (
                      <>
                        <Pause className="mr-2 h-4 w-4" />
                        Pause
                      </>
                    ) : (
                      <>
                        <Play className="mr-2 h-4 w-4" />
                        Start
                      </>
                    )}
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleAIAnalysis}
                    disabled={aiTrading.isAnalyzing || klines.length < 50}
                  >
                    {aiTrading.isAnalyzing ? (
                      <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                    ) : (
                      <Zap className="mr-2 h-4 w-4" />
                    )}
                    AI Analyze
                  </Button>
                </div>
              </div>

              {/* Main Grid - 3 columns, fills remaining space */}
              <div className="grid flex-1 gap-4 overflow-hidden lg:grid-cols-12">
                {/* Left Column - Chart & Price (5 cols) */}
                <div className="flex flex-col gap-4 overflow-hidden lg:col-span-5">
                  <Card className="flex-1 overflow-hidden">
                    <CardHeader className="pb-2">
                      <div className="flex items-center justify-between">
                        <CardTitle className="text-lg">{selectedSymbol}</CardTitle>
                        <div className="flex gap-1">
                          {["1m", "5m", "15m", "1h", "4h"].map((tf) => (
                            <Button
                              key={tf}
                              variant={selectedTimeframe === tf ? "default" : "ghost"}
                              size="sm"
                              className="h-6 px-2 text-xs"
                              onClick={() => setSelectedTimeframe(tf)}
                            >
                              {tf}
                            </Button>
                          ))}
                        </div>
                      </div>
                    </CardHeader>
                    <CardContent className="h-[calc(100%-4rem)] pb-2">
                      {isLoadingKlines ? (
                        <div className="flex h-full items-center justify-center">
                          <div className="text-center">
                            <RefreshCw className="mx-auto h-8 w-8 animate-spin text-muted-foreground/50" />
                            <p className="mt-2 text-sm text-muted-foreground">Loading chart...</p>
                          </div>
                        </div>
                      ) : klines.length > 0 ? (
                        <SimpleKlineChart klines={klines} />
                      ) : (
                        <div className="flex h-full items-center justify-center">
                          <p className="text-sm text-muted-foreground">No chart data available</p>
                        </div>
                      )}
                    </CardContent>
                  </Card>
                </div>

                {/* Middle Column - AI Decision & Indicators (4 cols) */}
                <div className="flex flex-col gap-4 overflow-hidden lg:col-span-4">
                  {/* AI Decision */}
                  <Card className="flex-none">
                    <CardHeader className="pb-3">
                      <CardTitle className="text-base">AI Decision</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-3">
                      {aiTrading.latestAnalysis ? (
                        <>
                          <div className="flex items-center justify-between">
                            <span className="text-sm text-muted-foreground">Action</span>
                            <Badge
                              variant={
                                aiTrading.latestAnalysis.decision.action.includes("LONG")
                                  ? "default"
                                  : aiTrading.latestAnalysis.decision.action.includes("SHORT")
                                    ? "destructive"
                                    : "secondary"
                              }
                              className="text-xs"
                            >
                              {aiTrading.latestAnalysis.decision.action}
                            </Badge>
                          </div>
                          <div className="flex items-center justify-between">
                            <span className="text-sm text-muted-foreground">Confidence</span>
                            <span className="font-mono text-sm font-medium">
                              {(aiTrading.latestAnalysis.decision.confidence * 100).toFixed(1)}%
                            </span>
                          </div>
                          <div>
                            <span className="text-xs text-muted-foreground">Reasoning</span>
                            <p className="mt-1 text-xs leading-relaxed">
                              {aiTrading.latestAnalysis.decision.reasoning}
                            </p>
                          </div>
                        </>
                      ) : (
                        <p className="text-center text-xs text-muted-foreground">
                          Click "AI Analyze" to get trading signal
                        </p>
                      )}
                    </CardContent>
                  </Card>

                  {/* Indicators */}
                  <Card className="flex-1 overflow-hidden">
                    <CardHeader className="pb-3">
                      <div className="flex items-center justify-between">
                        <CardTitle className="text-base">Technical Indicators</CardTitle>
                        {isLive && (
                          <Badge variant="outline" className="text-xs">
                            <Activity className="mr-1 h-3 w-3" />
                            Live
                          </Badge>
                        )}
                      </div>
                    </CardHeader>
                    <CardContent className="h-[calc(100%-4rem)] overflow-auto pb-2">
                      {indicators ? (
                        <div className="space-y-2">
                          {/* RSI */}
                          <div className="flex items-center justify-between text-xs">
                            <span className="text-muted-foreground">RSI (14)</span>
                            <span
                              className={cn(
                                "font-mono font-medium",
                                indicators.rsi > 70
                                  ? "text-red-500"
                                  : indicators.rsi < 30
                                    ? "text-green-500"
                                    : ""
                              )}
                            >
                              {indicators.rsi.toFixed(2)}
                            </span>
                          </div>

                          {/* MACD */}
                          <div className="space-y-1">
                            <div className="flex items-center justify-between text-xs">
                              <span className="text-muted-foreground">MACD</span>
                              <span className="font-mono text-xs">{indicators.macd.macd.toFixed(2)}</span>
                            </div>
                            <div className="flex items-center justify-between text-xs">
                              <span className="pl-2 text-muted-foreground">Signal</span>
                              <span className="font-mono text-xs">{indicators.macd.signal.toFixed(2)}</span>
                            </div>
                            <div className="flex items-center justify-between text-xs">
                              <span className="pl-2 text-muted-foreground">Histogram</span>
                              <span
                                className={cn(
                                  "font-mono text-xs",
                                  indicators.macd.histogram > 0 ? "text-green-500" : "text-red-500"
                                )}
                              >
                                {indicators.macd.histogram.toFixed(2)}
                              </span>
                            </div>
                          </div>

                          {/* EMAs */}
                          <div className="space-y-1">
                            <div className="flex items-center justify-between text-xs">
                              <span className="text-muted-foreground">EMA 9</span>
                              <span className="font-mono text-xs">{indicators.ema9.toFixed(2)}</span>
                            </div>
                            <div className="flex items-center justify-between text-xs">
                              <span className="text-muted-foreground">EMA 21</span>
                              <span className="font-mono text-xs">{indicators.ema21.toFixed(2)}</span>
                            </div>
                            <div className="flex items-center justify-between text-xs">
                              <span className="text-muted-foreground">EMA 50</span>
                              <span className="font-mono text-xs">{indicators.ema50.toFixed(2)}</span>
                            </div>
                          </div>

                          {/* Bollinger Bands */}
                          <div className="space-y-1">
                            <div className="flex items-center justify-between text-xs">
                              <span className="text-muted-foreground">BB Upper</span>
                              <span className="font-mono text-xs">{indicators.boll.upper.toFixed(2)}</span>
                            </div>
                            <div className="flex items-center justify-between text-xs">
                              <span className="text-muted-foreground">BB Middle</span>
                              <span className="font-mono text-xs">{indicators.boll.middle.toFixed(2)}</span>
                            </div>
                            <div className="flex items-center justify-between text-xs">
                              <span className="text-muted-foreground">BB Lower</span>
                              <span className="font-mono text-xs">{indicators.boll.lower.toFixed(2)}</span>
                            </div>
                          </div>

                          {/* Other indicators */}
                          <div className="flex items-center justify-between text-xs">
                            <span className="text-muted-foreground">ATR (14)</span>
                            <span className="font-mono text-xs">{indicators.atr.toFixed(2)}</span>
                          </div>
                          <div className="flex items-center justify-between text-xs">
                            <span className="text-muted-foreground">ADX (14)</span>
                            <span className="font-mono text-xs">{indicators.adx.toFixed(2)}</span>
                          </div>
                        </div>
                      ) : (
                        <p className="text-center text-xs text-muted-foreground">
                          Waiting for sufficient data...
                        </p>
                      )}
                    </CardContent>
                  </Card>
                </div>

                {/* Right Column - Actions & Stats (3 cols) */}
                <div className="flex flex-col gap-4 overflow-hidden lg:col-span-3">
                  {/* Performance Stats */}
                  <Card className="flex-none">
                    <CardHeader className="pb-3">
                      <CardTitle className="text-base">Performance</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-2">
                      <div className="flex items-center justify-between text-xs">
                        <span className="text-muted-foreground">Win Rate</span>
                        <span className="font-mono font-medium text-green-500">
                          {agent.performance?.winRate.toFixed(1) ?? "0"}%
                        </span>
                      </div>
                      <div className="flex items-center justify-between text-xs">
                        <span className="text-muted-foreground">Total Trades</span>
                        <span className="font-mono">{agent.performance?.totalTrades ?? 0}</span>
                      </div>
                      <div className="flex items-center justify-between text-xs">
                        <span className="text-muted-foreground">P&L</span>
                        <span
                          className={cn(
                            "font-mono font-medium",
                            (agent.performance?.pnl ?? 0) >= 0 ? "text-green-500" : "text-red-500"
                          )}
                        >
                          {(agent.performance?.pnl ?? 0) >= 0 ? "+" : ""}
                          {agent.performance?.pnl?.toFixed(2) ?? "0.00"}
                        </span>
                      </div>
                    </CardContent>
                  </Card>

                  {/* Recent Actions */}
                  <Card className="flex-1 overflow-hidden">
                    <CardHeader className="pb-3">
                      <div className="flex items-center justify-between">
                        <CardTitle className="text-base">Recent Actions</CardTitle>
                        {tradingActions.isLoading && (
                          <RefreshCw className="h-3 w-3 animate-spin text-muted-foreground" />
                        )}
                      </div>
                    </CardHeader>
                    <CardContent className="h-[calc(100%-4rem)] overflow-auto pb-2">
                      <div className="space-y-2">
                        {tradingActions.actions.length > 0 ? (
                          tradingActions.actions.slice(0, 10).map((action) => (
                            <div key={action.id} className="rounded-md border bg-muted/20 p-2">
                              <div className="flex items-start justify-between">
                                <div className="flex items-center gap-2">
                                  {action.action.includes("LONG") ? (
                                    <TrendingUp className="h-4 w-4 flex-shrink-0 text-green-500" />
                                  ) : action.action.includes("SHORT") ? (
                                    <TrendingDown className="h-4 w-4 flex-shrink-0 text-red-500" />
                                  ) : (
                                    <Activity className="h-4 w-4 flex-shrink-0 text-muted-foreground" />
                                  )}
                                  <div className="min-w-0 flex-1">
                                    <p className="text-xs font-medium">{action.action}</p>
                                    <p className="text-xs text-muted-foreground">
                                      {new Date(action.timestamp).toLocaleTimeString()}
                                    </p>
                                  </div>
                                </div>
                                <Badge variant="outline" className="flex-shrink-0 text-xs">
                                  {(action.confidence * 100).toFixed(0)}%
                                </Badge>
                              </div>
                              {action.price && (
                                <p className="mt-1 text-xs text-muted-foreground">
                                  ${action.price.toFixed(2)}
                                </p>
                              )}
                            </div>
                          ))
                        ) : (
                          <p className="text-center text-xs text-muted-foreground">
                            {tradingActions.error
                              ? "Failed to load actions"
                              : "No trading actions yet"}
                          </p>
                        )}
                      </div>
                    </CardContent>
                  </Card>
                </div>
              </div>
            </div>
          </main>
        </div>
      </div>
    </ProtectedRoute>
  )
}
