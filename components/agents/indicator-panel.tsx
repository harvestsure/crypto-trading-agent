"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import { cn } from "@/lib/utils"

interface IndicatorPanelProps {
  indicators: string[]
}

interface IndicatorValue {
  name: string
  value: number
  description: string
  status: "bullish" | "bearish" | "neutral"
}

export function IndicatorPanel({ indicators }: IndicatorPanelProps) {
  const [values, setValues] = useState<IndicatorValue[]>([])

  useEffect(() => {
    // Generate initial indicator values
    const generateValues = () => {
      const indicatorData: Record<string, () => IndicatorValue> = {
        RSI: () => {
          const value = Math.random() * 100
          return {
            name: "RSI (14)",
            value: Math.round(value * 100) / 100,
            description: value > 70 ? "Overbought" : value < 30 ? "Oversold" : "Neutral",
            status: value > 70 ? "bearish" : value < 30 ? "bullish" : "neutral",
          }
        },
        ADX: () => {
          const value = Math.random() * 60 + 10
          return {
            name: "ADX (14)",
            value: Math.round(value * 100) / 100,
            description: value > 25 ? "Strong Trend" : "Weak Trend",
            status: value > 25 ? "bullish" : "neutral",
          }
        },
        CHOP: () => {
          const value = Math.random() * 40 + 30
          return {
            name: "Choppiness",
            value: Math.round(value * 100) / 100,
            description: value > 61.8 ? "Choppy" : value < 38.2 ? "Trending" : "Consolidating",
            status: value < 38.2 ? "bullish" : value > 61.8 ? "bearish" : "neutral",
          }
        },
        KAMA: () => {
          const value = 43000 + (Math.random() - 0.5) * 1000
          return {
            name: "KAMA (10)",
            value: Math.round(value * 100) / 100,
            description: "Adaptive MA",
            status: "neutral",
          }
        },
        MACD: () => {
          const value = (Math.random() - 0.5) * 200
          return {
            name: "MACD",
            value: Math.round(value * 100) / 100,
            description: value > 0 ? "Bullish" : "Bearish",
            status: value > 0 ? "bullish" : "bearish",
          }
        },
        EMA: () => ({
          name: "EMA (20)",
          value: Math.round((42800 + Math.random() * 400) * 100) / 100,
          description: "Exponential MA",
          status: "neutral",
        }),
        SMA: () => ({
          name: "SMA (20)",
          value: Math.round((42700 + Math.random() * 400) * 100) / 100,
          description: "Simple MA",
          status: "neutral",
        }),
        BB: () => ({
          name: "Bollinger %B",
          value: Math.round(Math.random() * 100) / 100,
          description: Math.random() > 0.5 ? "Upper Band" : "Lower Band",
          status: "neutral",
        }),
        ATR: () => ({
          name: "ATR (14)",
          value: Math.round((500 + Math.random() * 300) * 100) / 100,
          description: "Volatility",
          status: "neutral",
        }),
        VWAP: () => ({
          name: "VWAP",
          value: Math.round((42900 + Math.random() * 200) * 100) / 100,
          description: "Volume Weighted",
          status: "neutral",
        }),
      }

      return indicators.filter((ind) => indicatorData[ind]).map((ind) => indicatorData[ind]())
    }

    setValues(generateValues())

    // Update values periodically
    const interval = setInterval(() => {
      setValues(generateValues())
    }, 5000)

    return () => clearInterval(interval)
  }, [indicators])

  return (
    <Card className="h-full">
      <CardHeader className="pb-3">
        <CardTitle className="text-base">Technical Indicators</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {values.map((indicator) => (
          <div key={indicator.name} className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">{indicator.name}</span>
              <span
                className={cn(
                  "font-medium",
                  indicator.status === "bullish" && "text-success",
                  indicator.status === "bearish" && "text-destructive",
                  indicator.status === "neutral" && "text-foreground",
                )}
              >
                {indicator.name.includes("RSI") || indicator.name.includes("Chop") || indicator.name.includes("%B")
                  ? indicator.value.toFixed(2)
                  : indicator.value.toLocaleString()}
              </span>
            </div>

            {(indicator.name.includes("RSI") || indicator.name.includes("Chop")) && (
              <Progress
                value={indicator.value}
                className={cn(
                  "h-2",
                  indicator.status === "bullish" && "[&>div]:bg-success",
                  indicator.status === "bearish" && "[&>div]:bg-destructive",
                )}
              />
            )}

            <p className="text-xs text-muted-foreground">{indicator.description}</p>
          </div>
        ))}

        {values.length === 0 && (
          <p className="text-center text-sm text-muted-foreground py-4">No indicators configured</p>
        )}
      </CardContent>
    </Card>
  )
}
