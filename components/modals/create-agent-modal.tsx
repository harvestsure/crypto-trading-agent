"use client"

import type React from "react"
import { useState } from "react"
import { useAppStore } from "@/lib/store"
import { useModels, useExchanges } from "@/hooks/use-data"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"
import { Badge } from "@/components/ui/badge"
import { X, Loader2 } from "lucide-react"

interface CreateAgentModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSuccess?: () => void // Added onSuccess callback for refetching
}

const timeframes = [
  { value: "1m", label: "1 minute" },
  { value: "5m", label: "5 minutes" },
  { value: "15m", label: "15 minutes" },
  { value: "30m", label: "30 minutes" },
  { value: "1h", label: "1 hour" },
  { value: "4h", label: "4 hours" },
  { value: "1d", label: "1 day" },
]

const availableIndicators = ["RSI", "MACD", "ADX", "CHOP", "KAMA", "EMA", "SMA", "BB", "ATR", "VWAP"]

const defaultPrompt = `You are a cryptocurrency trading AI agent. Analyze the market data and technical indicators provided to make trading decisions.

Based on the K-line data and indicators (ADX, CHOP, KAMA, etc.), output one of the following actions:
- BUY: Open a long position with suggested take profit and stop loss levels
- SELL: Close position or open a short position
- HOLD: Maintain current position

Consider:
1. Trend strength from ADX
2. Market choppiness from CHOP
3. Adaptive moving average from KAMA
4. Risk management with proper position sizing

Respond in JSON format:
{
  "action": "BUY|SELL|HOLD",
  "reason": "brief explanation",
  "takeProfit": number (percentage),
  "stopLoss": number (percentage)
}`

export function CreateAgentModal({ open, onOpenChange, onSuccess }: CreateAgentModalProps) {
  const { models } = useModels()
  const { exchanges } = useExchanges()
  const { createAgent, isCreatingAgent } = useAppStore()
  const [error, setError] = useState<string | null>(null)
  const [formData, setFormData] = useState({
    name: "",
    modelId: "",
    exchangeId: "",
    symbol: "BTC/USDT",
    timeframe: "1h" as const,
    indicators: ["RSI", "ADX", "CHOP"] as string[],
    prompt: defaultPrompt,
  })

  const toggleIndicator = (indicator: string) => {
    setFormData((prev) => ({
      ...prev,
      indicators: prev.indicators.includes(indicator)
        ? prev.indicators.filter((i) => i !== indicator)
        : [...prev.indicators, indicator],
    }))
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    const result = await createAgent({
      name: formData.name,
      modelId: formData.modelId,
      exchangeId: formData.exchangeId,
      symbol: formData.symbol,
      timeframe: formData.timeframe,
      indicators: formData.indicators,
      prompt: formData.prompt,
    })

    if (result.success) {
      setFormData({
        name: "",
        modelId: "",
        exchangeId: "",
        symbol: "BTC/USDT",
        timeframe: "1h",
        indicators: ["RSI", "ADX", "CHOP"],
        prompt: defaultPrompt,
      })
      onOpenChange(false)
      onSuccess?.()
    } else {
      setError(result.error || "Failed to create agent")
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[600px] max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Create Trading Agent</DialogTitle>
          <DialogDescription>Configure a new AI-powered trading agent.</DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit}>
          <div className="grid gap-4 py-4">
            {error && <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">{error}</div>}

            <div className="grid gap-2">
              <Label htmlFor="name">Agent Name</Label>
              <Input
                id="name"
                placeholder="BTC Trend Follower"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                required
                disabled={isCreatingAgent}
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="grid gap-2">
                <Label htmlFor="model">AI Model</Label>
                <Select
                  value={formData.modelId}
                  onValueChange={(value) => setFormData({ ...formData, modelId: value })}
                  disabled={isCreatingAgent}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select model" />
                  </SelectTrigger>
                  <SelectContent>
                    {models.map((model) => (
                      <SelectItem key={model.id} value={model.id}>
                        {model.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="grid gap-2">
                <Label htmlFor="exchange">Exchange</Label>
                <Select
                  value={formData.exchangeId}
                  onValueChange={(value) => setFormData({ ...formData, exchangeId: value })}
                  disabled={isCreatingAgent}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select exchange" />
                  </SelectTrigger>
                  <SelectContent>
                    {exchanges.map((exchange) => (
                      <SelectItem key={exchange.id} value={exchange.id}>
                        {exchange.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="grid gap-2">
                <Label htmlFor="symbol">Trading Pair</Label>
                <Input
                  id="symbol"
                  placeholder="BTC/USDT"
                  value={formData.symbol}
                  onChange={(e) => setFormData({ ...formData, symbol: e.target.value })}
                  required
                  disabled={isCreatingAgent}
                />
              </div>

              <div className="grid gap-2">
                <Label htmlFor="timeframe">Timeframe</Label>
                <Select
                  value={formData.timeframe}
                  onValueChange={(value: "1m" | "5m" | "15m" | "30m" | "1h" | "4h" | "1d") =>
                    setFormData({ ...formData, timeframe: value })
                  }
                  disabled={isCreatingAgent}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {timeframes.map((tf) => (
                      <SelectItem key={tf.value} value={tf.value}>
                        {tf.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="grid gap-2">
              <Label>Technical Indicators</Label>
              <div className="flex flex-wrap gap-2">
                {availableIndicators.map((indicator) => (
                  <Badge
                    key={indicator}
                    variant={formData.indicators.includes(indicator) ? "default" : "outline"}
                    className="cursor-pointer"
                    onClick={() => !isCreatingAgent && toggleIndicator(indicator)}
                  >
                    {indicator}
                    {formData.indicators.includes(indicator) && <X className="ml-1 h-3 w-3" />}
                  </Badge>
                ))}
              </div>
            </div>

            <div className="grid gap-2">
              <Label htmlFor="prompt">System Prompt</Label>
              <Textarea
                id="prompt"
                rows={8}
                className="font-mono text-sm"
                value={formData.prompt}
                onChange={(e) => setFormData({ ...formData, prompt: e.target.value })}
                required
                disabled={isCreatingAgent}
              />
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={isCreatingAgent}>
              Cancel
            </Button>
            <Button type="submit" disabled={!formData.modelId || !formData.exchangeId || isCreatingAgent}>
              {isCreatingAgent && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Create Agent
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
