/**
 * AI Trading Hook
 * Provides real-time AI analysis and trading decisions
 */

import { useState, useCallback, useEffect, useRef } from "react"
import { calculateAllIndicators, type IndicatorResults, type KlineData } from "@/lib/indicators"

export interface TradingDecision {
  action: "LONG" | "SHORT" | "CLOSE_LONG" | "CLOSE_SHORT" | "HOLD"
  confidence: number
  reasoning: string
  stopLoss?: number
  takeProfit?: number
  positionSize: number
}

export interface AnalysisResult {
  decision: TradingDecision
  indicators: IndicatorResults
  timestamp: number
}

export interface UseAITradingOptions {
  symbol: string
  timeframe: string
  customPrompt?: string
  riskTolerance?: "low" | "medium" | "high"
  autoAnalyze?: boolean
  analyzeInterval?: number // in milliseconds
}

export function useAITrading(options: UseAITradingOptions) {
  const {
    symbol,
    timeframe,
    customPrompt,
    riskTolerance = "medium",
    autoAnalyze = false,
    analyzeInterval = 60000, // 1 minute default
  } = options

  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [latestAnalysis, setLatestAnalysis] = useState<AnalysisResult | null>(null)
  const [analysisHistory, setAnalysisHistory] = useState<AnalysisResult[]>([])
  const [error, setError] = useState<string | null>(null)
  const intervalRef = useRef<NodeJS.Timeout | null>(null)

  /**
   * Analyze market data with AI
   */
  const analyze = useCallback(
    async (klines: KlineData[]): Promise<AnalysisResult | null> => {
      if (klines.length < 50) {
        setError("Insufficient data for analysis (minimum 50 candles required)")
        return null
      }

      setIsAnalyzing(true)
      setError(null)

      try {
        const response = await fetch("/api/trading/analyze", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            symbol,
            timeframe,
            klines,
            customPrompt,
            riskTolerance,
          }),
        })

        if (!response.ok) {
          const errorData = await response.json()
          throw new Error(errorData.error || "Analysis failed")
        }

        const result = await response.json()

        const analysisResult: AnalysisResult = {
          decision: result.decision,
          indicators: result.indicators,
          timestamp: result.timestamp,
        }

        setLatestAnalysis(analysisResult)
        setAnalysisHistory((prev) => [...prev, analysisResult].slice(-50)) // Keep last 50 analyses

        console.log("[v0] AI Trading Decision:", analysisResult.decision)

        return analysisResult
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : "Unknown error"
        setError(errorMessage)
        console.error("[v0] AI analysis error:", errorMessage)
        return null
      } finally {
        setIsAnalyzing(false)
      }
    },
    [symbol, timeframe, customPrompt, riskTolerance],
  )

  /**
   * Calculate indicators locally (client-side)
   */
  const calculateIndicators = useCallback((klines: KlineData[]): IndicatorResults => {
    return calculateAllIndicators(klines)
  }, [])

  /**
   * Get trading signal strength
   */
  const getSignalStrength = useCallback((): "strong" | "moderate" | "weak" | "none" => {
    if (!latestAnalysis) return "none"

    const confidence = latestAnalysis.decision.confidence

    if (confidence >= 0.8) return "strong"
    if (confidence >= 0.6) return "moderate"
    if (confidence >= 0.4) return "weak"
    return "none"
  }, [latestAnalysis])

  /**
   * Get recommended action
   */
  const getRecommendedAction = useCallback((): string => {
    if (!latestAnalysis) return "Waiting for analysis..."

    const { action, confidence } = latestAnalysis.decision
    const strength = getSignalStrength()

    if (action === "HOLD") {
      return "No clear signal - stay on sidelines"
    }

    return `${action} (${strength} signal, ${(confidence * 100).toFixed(0)}% confidence)`
  }, [latestAnalysis, getSignalStrength])

  /**
   * Setup auto-analysis interval
   */
  useEffect(() => {
    if (!autoAnalyze) {
      if (intervalRef.current) {
        clearInterval(intervalRef.current)
        intervalRef.current = null
      }
      return
    }

    // Auto-analyze will be triggered externally with kline data
    // This is just a placeholder for future WebSocket integration

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current)
        intervalRef.current = null
      }
    }
  }, [autoAnalyze, analyzeInterval])

  return {
    // State
    isAnalyzing,
    latestAnalysis,
    analysisHistory,
    error,

    // Methods
    analyze,
    calculateIndicators,
    getSignalStrength,
    getRecommendedAction,
  }
}
