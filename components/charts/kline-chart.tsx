"use client"

import { useState, useEffect, useMemo } from "react"
import { cn } from "@/lib/utils"

interface KlineChartProps {
  symbol: string
  timeframe: string
}

interface Candle {
  timestamp: number
  open: number
  high: number
  low: number
  close: number
  volume: number
}

// Generate mock kline data
function generateMockKlines(count: number, basePrice: number): Candle[] {
  const klines: Candle[] = []
  let price = basePrice
  const now = Date.now()

  for (let i = count - 1; i >= 0; i--) {
    const volatility = price * 0.02
    const open = price
    const change = (Math.random() - 0.5) * volatility
    const close = open + change
    const high = Math.max(open, close) + Math.random() * volatility * 0.5
    const low = Math.min(open, close) - Math.random() * volatility * 0.5
    const volume = Math.random() * 1000000 + 500000

    klines.push({
      timestamp: now - i * 3600000, // 1 hour intervals
      open,
      high,
      low,
      close,
      volume,
    })

    price = close
  }

  return klines
}

export function KlineChart({ symbol, timeframe }: KlineChartProps) {
  const [klines, setKlines] = useState<Candle[]>([])
  const [hoveredCandle, setHoveredCandle] = useState<Candle | null>(null)

  useEffect(() => {
    // Initial data
    const basePrice = symbol.includes("BTC") ? 43000 : symbol.includes("ETH") ? 2200 : 100
    setKlines(generateMockKlines(50, basePrice))

    // Simulate real-time updates
    const interval = setInterval(() => {
      setKlines((prev) => {
        if (prev.length === 0) return prev
        const lastCandle = prev[prev.length - 1]
        const volatility = lastCandle.close * 0.005
        const newClose = lastCandle.close + (Math.random() - 0.5) * volatility

        // Update last candle
        const updated = [...prev]
        updated[updated.length - 1] = {
          ...lastCandle,
          close: newClose,
          high: Math.max(lastCandle.high, newClose),
          low: Math.min(lastCandle.low, newClose),
        }
        return updated
      })
    }, 2000)

    return () => clearInterval(interval)
  }, [symbol])

  const { minPrice, maxPrice, chartHeight, candleWidth } = useMemo(() => {
    if (klines.length === 0) return { minPrice: 0, maxPrice: 0, chartHeight: 300, candleWidth: 8 }

    const prices = klines.flatMap((k) => [k.high, k.low])
    const min = Math.min(...prices)
    const max = Math.max(...prices)
    const padding = (max - min) * 0.1

    return {
      minPrice: min - padding,
      maxPrice: max + padding,
      chartHeight: 300,
      candleWidth: Math.max(4, Math.min(12, 600 / klines.length - 2)),
    }
  }, [klines])

  const priceToY = (price: number) => {
    const range = maxPrice - minPrice
    if (range === 0) return chartHeight / 2
    return chartHeight - ((price - minPrice) / range) * chartHeight
  }

  return (
    <div className="relative">
      {/* Price Info */}
      {hoveredCandle && (
        <div className="absolute left-2 top-2 z-10 rounded-lg border border-border bg-card p-2 text-xs shadow-lg">
          <div className="grid grid-cols-2 gap-x-4 gap-y-1">
            <span className="text-muted-foreground">Open:</span>
            <span className="text-foreground">${hoveredCandle.open.toFixed(2)}</span>
            <span className="text-muted-foreground">High:</span>
            <span className="text-success">${hoveredCandle.high.toFixed(2)}</span>
            <span className="text-muted-foreground">Low:</span>
            <span className="text-destructive">${hoveredCandle.low.toFixed(2)}</span>
            <span className="text-muted-foreground">Close:</span>
            <span className="text-foreground">${hoveredCandle.close.toFixed(2)}</span>
            <span className="text-muted-foreground">Volume:</span>
            <span className="text-foreground">{(hoveredCandle.volume / 1000000).toFixed(2)}M</span>
          </div>
        </div>
      )}

      {/* Chart */}
      <svg
        viewBox={`0 0 ${klines.length * (candleWidth + 2)} ${chartHeight}`}
        className="w-full h-[300px]"
        preserveAspectRatio="none"
      >
        {/* Grid lines */}
        {[0, 0.25, 0.5, 0.75, 1].map((ratio) => (
          <line
            key={ratio}
            x1={0}
            y1={ratio * chartHeight}
            x2={klines.length * (candleWidth + 2)}
            y2={ratio * chartHeight}
            className="stroke-border"
            strokeWidth={0.5}
          />
        ))}

        {/* Candles */}
        {klines.map((candle, index) => {
          const x = index * (candleWidth + 2)
          const isGreen = candle.close >= candle.open
          const bodyTop = priceToY(Math.max(candle.open, candle.close))
          const bodyBottom = priceToY(Math.min(candle.open, candle.close))
          const bodyHeight = Math.max(1, bodyBottom - bodyTop)
          const wickTop = priceToY(candle.high)
          const wickBottom = priceToY(candle.low)

          return (
            <g
              key={candle.timestamp}
              onMouseEnter={() => setHoveredCandle(candle)}
              onMouseLeave={() => setHoveredCandle(null)}
              className="cursor-crosshair"
            >
              {/* Wick */}
              <line
                x1={x + candleWidth / 2}
                y1={wickTop}
                x2={x + candleWidth / 2}
                y2={wickBottom}
                className={cn(isGreen ? "stroke-success" : "stroke-destructive")}
                strokeWidth={1}
              />
              {/* Body */}
              <rect
                x={x}
                y={bodyTop}
                width={candleWidth}
                height={bodyHeight}
                className={cn(isGreen ? "fill-success" : "fill-destructive")}
                rx={1}
              />
            </g>
          )
        })}
      </svg>

      {/* Price Scale */}
      <div className="absolute right-0 top-0 flex h-[300px] flex-col justify-between py-1 text-right text-xs text-muted-foreground">
        <span>${maxPrice.toFixed(2)}</span>
        <span>${((maxPrice + minPrice) / 2).toFixed(2)}</span>
        <span>${minPrice.toFixed(2)}</span>
      </div>
    </div>
  )
}
