"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import { Separator } from "@/components/ui/separator"
import { cn } from "@/lib/utils"
import { TrendingUp, TrendingDown, Activity, AlertCircle } from "lucide-react"
import type { IndicatorResults } from "@/lib/indicators"

interface LiveIndicatorPanelProps {
  indicators?: IndicatorResults
  isLive?: boolean
  symbol?: string
}

export function LiveIndicatorPanel({ indicators, isLive = false, symbol }: LiveIndicatorPanelProps) {
  if (!indicators) {
    return (
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center justify-between">
            <span>Technical Indicators</span>
            {symbol && <span className="text-xs text-muted-foreground font-normal">{symbol}</span>}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col items-center justify-center py-8 text-center">
            <AlertCircle className="h-8 w-8 text-muted-foreground mb-2" />
            <p className="text-sm text-muted-foreground">No indicator data available</p>
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base flex items-center justify-between">
          <span>Technical Indicators</span>
          <div className="flex items-center gap-2">
            {symbol && <span className="text-xs text-muted-foreground font-normal">{symbol}</span>}
            {isLive && (
              <Badge variant="default" className="text-xs">
                <Activity className="h-3 w-3 mr-1 animate-pulse" />
                Live
              </Badge>
            )}
          </div>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* RSI */}
        {indicators.rsi !== undefined && (
          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">RSI (14)</span>
              <span
                className={cn(
                  "font-semibold",
                  indicators.rsi > 70 && "text-destructive",
                  indicators.rsi < 30 && "text-success",
                  indicators.rsi >= 30 && indicators.rsi <= 70 && "text-foreground",
                )}
              >
                {indicators.rsi.toFixed(2)}
              </span>
            </div>
            <Progress
              value={indicators.rsi}
              className={cn(
                "h-2",
                indicators.rsi > 70 && "[&>div]:bg-destructive",
                indicators.rsi < 30 && "[&>div]:bg-success",
              )}
            />
            <p className="text-xs text-muted-foreground">
              {indicators.rsi > 70 ? "Overbought" : indicators.rsi < 30 ? "Oversold" : "Neutral"}
            </p>
          </div>
        )}

        {/* MACD */}
        {indicators.macd && (
          <>
            <Separator />
            <div className="space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">MACD</span>
                <div className="flex items-center gap-2">
                  {indicators.macd.histogram > 0 ? (
                    <TrendingUp className="h-3 w-3 text-success" />
                  ) : (
                    <TrendingDown className="h-3 w-3 text-destructive" />
                  )}
                  <span
                    className={cn(
                      "font-semibold",
                      indicators.macd.histogram > 0 ? "text-success" : "text-destructive",
                    )}
                  >
                    {indicators.macd.macd.toFixed(2)}
                  </span>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Signal:</span>
                  <span>{indicators.macd.signal.toFixed(2)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Histogram:</span>
                  <span>{indicators.macd.histogram.toFixed(2)}</span>
                </div>
              </div>
              <p className="text-xs text-muted-foreground">
                {indicators.macd.histogram > 0 ? "Bullish momentum" : "Bearish momentum"}
              </p>
            </div>
          </>
        )}

        {/* EMAs */}
        {indicators.ema && (
          <>
            <Separator />
            <div className="space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground font-semibold">EMAs</span>
              </div>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">EMA 9:</span>
                  <span className="font-medium">${indicators.ema.ema9.toLocaleString()}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">EMA 21:</span>
                  <span className="font-medium">${indicators.ema.ema21.toLocaleString()}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">EMA 50:</span>
                  <span className="font-medium">${indicators.ema.ema50.toLocaleString()}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">EMA 200:</span>
                  <span className="font-medium">${indicators.ema.ema200.toLocaleString()}</span>
                </div>
              </div>
            </div>
          </>
        )}

        {/* Bollinger Bands */}
        {indicators.bollinger && (
          <>
            <Separator />
            <div className="space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground font-semibold">Bollinger Bands</span>
                <span className="text-xs text-muted-foreground">{indicators.bollinger.bandwidth.toFixed(2)}%</span>
              </div>
              <div className="space-y-1 text-xs">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Upper:</span>
                  <span className="font-medium">${indicators.bollinger.upper.toLocaleString()}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Middle:</span>
                  <span className="font-medium">${indicators.bollinger.middle.toLocaleString()}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Lower:</span>
                  <span className="font-medium">${indicators.bollinger.lower.toLocaleString()}</span>
                </div>
              </div>
            </div>
          </>
        )}

        {/* ADX */}
        {indicators.adx && (
          <>
            <Separator />
            <div className="space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">ADX (14)</span>
                <span
                  className={cn(
                    "font-semibold",
                    indicators.adx.adx > 25 ? "text-primary" : "text-muted-foreground",
                  )}
                >
                  {indicators.adx.adx.toFixed(2)}
                </span>
              </div>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">+DI:</span>
                  <span className="text-success">{indicators.adx.plusDI.toFixed(2)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">-DI:</span>
                  <span className="text-destructive">{indicators.adx.minusDI.toFixed(2)}</span>
                </div>
              </div>
              <p className="text-xs text-muted-foreground">
                {indicators.adx.adx > 25 ? "Strong trend" : "Weak trend"}{" "}
                {indicators.adx.plusDI > indicators.adx.minusDI ? "(Bullish)" : "(Bearish)"}
              </p>
            </div>
          </>
        )}

        {/* Stochastic */}
        {indicators.stochastic && (
          <>
            <Separator />
            <div className="space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Stochastic</span>
                <span
                  className={cn(
                    "font-semibold",
                    indicators.stochastic.k > 80 && "text-destructive",
                    indicators.stochastic.k < 20 && "text-success",
                    indicators.stochastic.k >= 20 &&
                      indicators.stochastic.k <= 80 &&
                      "text-foreground",
                  )}
                >
                  {indicators.stochastic.k.toFixed(2)}
                </span>
              </div>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">%K:</span>
                  <span>{indicators.stochastic.k.toFixed(2)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">%D:</span>
                  <span>{indicators.stochastic.d.toFixed(2)}</span>
                </div>
              </div>
              <p className="text-xs text-muted-foreground">
                {indicators.stochastic.k > 80
                  ? "Overbought"
                  : indicators.stochastic.k < 20
                  ? "Oversold"
                  : "Neutral"}
              </p>
            </div>
          </>
        )}

        {/* ATR */}
        {indicators.atr !== undefined && (
          <>
            <Separator />
            <div className="space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">ATR (14)</span>
                <span className="font-semibold">{indicators.atr.toFixed(2)}</span>
              </div>
              <p className="text-xs text-muted-foreground">Volatility measure</p>
            </div>
          </>
        )}

        {/* OBV & VWAP */}
        <Separator />
        <div className="grid grid-cols-2 gap-4 text-xs">
          {indicators.obv !== undefined && (
            <div className="space-y-1">
              <span className="text-muted-foreground">OBV</span>
              <p className="font-semibold text-sm">{indicators.obv.toLocaleString()}</p>
            </div>
          )}
          {indicators.vwap !== undefined && (
            <div className="space-y-1">
              <span className="text-muted-foreground">VWAP</span>
              <p className="font-semibold text-sm">${indicators.vwap.toLocaleString()}</p>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
