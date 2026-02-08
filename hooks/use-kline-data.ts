/**
 * Kline Data Hook
 * Manages real-time kline (candlestick) data with WebSocket updates
 */

import { useState, useEffect, useCallback, useRef } from "react"
import { wsService } from "@/lib/websocket"
import type { KlineData } from "@/lib/indicators"

export interface UseKlineDataOptions {
  exchangeId: string
  symbol: string
  timeframe: string
  limit?: number
  autoSubscribe?: boolean
}

export function useKlineData(options: UseKlineDataOptions) {
  const { exchangeId, symbol, timeframe, limit = 100, autoSubscribe = true } = options

  const [klines, setKlines] = useState<KlineData[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [isLive, setIsLive] = useState(false)
  const lastUpdateRef = useRef<number>(0)

  /**
   * Fetch initial kline data from API
   */
  const fetchKlines = useCallback(async () => {
    try {
      setIsLoading(true)
      setError(null)

      // In a real implementation, this would fetch from backend
      // For now, generate mock data
      const mockKlines: KlineData[] = []
      const now = Date.now()
      const timeframeMs = getTimeframeInMs(timeframe)

      let basePrice = 43000 + Math.random() * 1000

      for (let i = limit - 1; i >= 0; i--) {
        const timestamp = now - i * timeframeMs
        const open = basePrice
        const change = (Math.random() - 0.5) * 200
        const close = open + change
        const high = Math.max(open, close) + Math.random() * 50
        const low = Math.min(open, close) - Math.random() * 50
        const volume = 10 + Math.random() * 50

        mockKlines.push({
          timestamp,
          open: Math.round(open * 100) / 100,
          high: Math.round(high * 100) / 100,
          low: Math.round(low * 100) / 100,
          close: Math.round(close * 100) / 100,
          volume: Math.round(volume * 100) / 100,
        })

        basePrice = close
      }

      setKlines(mockKlines)
      setIsLoading(false)
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Failed to fetch klines"
      setError(errorMessage)
      setIsLoading(false)
      console.error("[v0] Failed to fetch klines:", errorMessage)
    }
  }, [symbol, timeframe, limit])

  /**
   * Subscribe to WebSocket kline updates
   */
  const subscribeToKlines = useCallback(() => {
    if (!wsService.isConnected) {
      console.log("[v0] WebSocket not connected, skipping kline subscription")
      return
    }

    console.log("[v0] Subscribing to klines:", { exchangeId, symbol, timeframe })
    wsService.subscribeKline(exchangeId, symbol, timeframe)
    setIsLive(true)
  }, [exchangeId, symbol, timeframe])

  /**
   * Handle WebSocket kline updates
   */
  useEffect(() => {
    const unsubscribe = wsService.onMessage((message) => {
      if (
        message.type === "kline" &&
        message.exchange_id === exchangeId &&
        message.symbol === symbol &&
        message.timeframe === timeframe
      ) {
        const klineMessage = message as any

        if (klineMessage.data && Array.isArray(klineMessage.data)) {
          setKlines(klineMessage.data)
          lastUpdateRef.current = Date.now()
        }
      }
    })

    return unsubscribe
  }, [exchangeId, symbol, timeframe])

  /**
   * Initial data fetch and subscription
   */
  useEffect(() => {
    fetchKlines()

    if (autoSubscribe && wsService.isConnected) {
      subscribeToKlines()
    }
  }, [fetchKlines, autoSubscribe, subscribeToKlines])

  /**
   * Simulate live updates when WebSocket is not connected
   */
  useEffect(() => {
    if (wsService.isConnected || klines.length === 0) return

    const interval = setInterval(() => {
      setKlines((prevKlines) => {
        if (prevKlines.length === 0) return prevKlines

        const lastKline = prevKlines[prevKlines.length - 1]
        const change = (Math.random() - 0.5) * 100
        const newClose = lastKline.close + change
        const newHigh = Math.max(lastKline.high, newClose + Math.random() * 20)
        const newLow = Math.min(lastKline.low, newClose - Math.random() * 20)

        const updatedKline = {
          ...lastKline,
          high: Math.round(newHigh * 100) / 100,
          low: Math.round(newLow * 100) / 100,
          close: Math.round(newClose * 100) / 100,
          volume: Math.round((lastKline.volume + Math.random() * 5) * 100) / 100,
        }

        return [...prevKlines.slice(0, -1), updatedKline]
      })

      lastUpdateRef.current = Date.now()
    }, 2000)

    return () => clearInterval(interval)
  }, [klines.length, wsService.isConnected])

  return {
    klines,
    isLoading,
    error,
    isLive,
    lastUpdate: lastUpdateRef.current,
    refetch: fetchKlines,
    subscribe: subscribeToKlines,
  }
}

/**
 * Helper function to convert timeframe to milliseconds
 */
function getTimeframeInMs(timeframe: string): number {
  const value = parseInt(timeframe)
  const unit = timeframe.replace(value.toString(), "")

  switch (unit) {
    case "m":
      return value * 60 * 1000
    case "h":
      return value * 60 * 60 * 1000
    case "d":
      return value * 24 * 60 * 60 * 1000
    default:
      return 60 * 1000 // default to 1 minute
  }
}
