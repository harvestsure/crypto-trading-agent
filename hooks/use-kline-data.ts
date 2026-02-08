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
    if (!exchangeId || !symbol || !timeframe) {
      console.log("[v0] Missing required parameters for kline fetch")
      return
    }

    try {
      setIsLoading(true)
      setError(null)

      console.log("[v0] Fetching klines:", { exchangeId, symbol, timeframe, limit })

      const response = await fetch(
        `/api/klines?exchangeId=${exchangeId}&symbol=${symbol}&timeframe=${timeframe}&limit=${limit}`
      )

      if (!response.ok) {
        throw new Error(`Failed to fetch klines: ${response.statusText}`)
      }

      const data = await response.json()

      if (data.error) {
        throw new Error(data.error)
      }

      // Transform backend data to KlineData format
      const klineData: KlineData[] = (data.klines || data).map((k: any) => ({
        timestamp: k.timestamp || k.time || k[0],
        open: parseFloat(k.open || k[1]),
        high: parseFloat(k.high || k[2]),
        low: parseFloat(k.low || k[3]),
        close: parseFloat(k.close || k[4]),
        volume: parseFloat(k.volume || k[5]),
      }))

      setKlines(klineData)
      setIsLoading(false)
      console.log("[v0] Loaded", klineData.length, "klines from API")
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Failed to fetch klines"
      setError(errorMessage)
      setIsLoading(false)
      console.error("[v0] Failed to fetch klines:", errorMessage)
    }
  }, [exchangeId, symbol, timeframe, limit])

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
   * Unsubscribe from WebSocket kline updates
   */
  const unsubscribeFromKlines = useCallback(() => {
    if (!wsService.isConnected) {
      return
    }

    console.log("[v0] Unsubscribing from klines:", { exchangeId, symbol, timeframe })
    wsService.unsubscribeKline(exchangeId, symbol, timeframe)
    setIsLive(false)
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
    unsubscribe: unsubscribeFromKlines,
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
