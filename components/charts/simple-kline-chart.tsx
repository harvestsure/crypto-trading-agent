"use client"

import { useMemo } from "react"
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, Area, AreaChart } from "recharts"
import type { KlineData } from "@/lib/indicators"

interface SimpleKlineChartProps {
  klines: KlineData[]
  height?: number
}

export function SimpleKlineChart({ klines, height = 400 }: SimpleKlineChartProps) {
  const chartData = useMemo(() => {
    return klines.map((kline) => ({
      time: new Date(kline.timestamp).toLocaleTimeString("en-US", {
        hour: "2-digit",
        minute: "2-digit",
      }),
      price: kline.close,
      high: kline.high,
      low: kline.low,
      volume: kline.volume,
    }))
  }, [klines])

  const minPrice = useMemo(() => Math.min(...klines.map((k) => k.low)), [klines])
  const maxPrice = useMemo(() => Math.max(...klines.map((k) => k.high)), [klines])
  const padding = (maxPrice - minPrice) * 0.1

  if (klines.length === 0) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
        No chart data available
      </div>
    )
  }

  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id="priceGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="hsl(var(--primary))" stopOpacity={0.3} />
            <stop offset="95%" stopColor="hsl(var(--primary))" stopOpacity={0} />
          </linearGradient>
        </defs>
        <XAxis
          dataKey="time"
          stroke="hsl(var(--muted-foreground))"
          fontSize={10}
          tickLine={false}
          axisLine={false}
          interval="preserveStartEnd"
          minTickGap={50}
        />
        <YAxis
          domain={[minPrice - padding, maxPrice + padding]}
          stroke="hsl(var(--muted-foreground))"
          fontSize={10}
          tickLine={false}
          axisLine={false}
          tickFormatter={(value) => `$${value.toFixed(0)}`}
          width={50}
        />
        <Tooltip
          content={({ active, payload }) => {
            if (!active || !payload || payload.length === 0) return null

            const data = payload[0].payload

            return (
              <div className="rounded-lg border bg-background p-2 shadow-md">
                <div className="grid gap-1">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs text-muted-foreground">Time</span>
                    <span className="text-xs font-medium">{data.time}</span>
                  </div>
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs text-muted-foreground">Price</span>
                    <span className="text-xs font-medium">${data.price.toFixed(2)}</span>
                  </div>
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs text-muted-foreground">High</span>
                    <span className="text-xs font-medium text-green-500">${data.high.toFixed(2)}</span>
                  </div>
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs text-muted-foreground">Low</span>
                    <span className="text-xs font-medium text-red-500">${data.low.toFixed(2)}</span>
                  </div>
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs text-muted-foreground">Volume</span>
                    <span className="text-xs font-medium">{data.volume.toFixed(2)}</span>
                  </div>
                </div>
              </div>
            )
          }}
        />
        <Area
          type="monotone"
          dataKey="price"
          stroke="hsl(var(--primary))"
          strokeWidth={2}
          fill="url(#priceGradient)"
          animationDuration={300}
        />
      </AreaChart>
    </ResponsiveContainer>
  )
}
