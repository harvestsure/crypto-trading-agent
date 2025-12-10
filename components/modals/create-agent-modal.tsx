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
import { X, Loader2, AlertCircle } from "lucide-react"
import { Alert, AlertDescription } from "@/components/ui/alert"

interface CreateAgentModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSuccess?: () => void
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

const defaultPrompt = `You are a professional cryptocurrency trading AI agent with expertise in technical analysis and risk management.

## Your Mission
Analyze real-time market data and technical indicators to make informed trading decisions while strictly adhering to risk management principles.

## Decision Framework

### Market Analysis
1. **Trend Identification**: Use KAMA and moving averages to determine market direction
2. **Strength Assessment**: Evaluate ADX (>25 = strong trend, <20 = weak/choppy)
3. **Momentum Analysis**: Check RSI for overbought (>70) or oversold (<30) conditions
4. **Volatility Measurement**: Monitor ATR and Bollinger Bands for risk assessment

### Risk Management Rules
- Maximum risk per trade: 2% of total capital
- Always set stop-loss orders immediately after opening positions
- Target risk-reward ratio: Minimum 1:2 (risk 1% to gain 2%)
- Avoid trading during high choppiness (CHOP > 61.8)
- Never increase position size when losing

### Entry Signals (ALL must align)
**For LONG positions:**
- ADX > 25 (strong trend)
- KAMA trending upward
- RSI between 40-70 (not overbought)
- CHOP < 50 (low choppiness)
- Price above key support levels

**For SHORT positions:**
- ADX > 25 (strong trend)
- KAMA trending downward
- RSI between 30-60 (not oversold)
- CHOP < 50 (low choppiness)
- Price below key resistance levels

### Exit Strategy
- Take profit at 2x stop-loss distance
- Trail stop-loss by 1 ATR when profit exceeds 1.5%
- Close position immediately if trend reverses (KAMA crossover)
- Exit during extreme volatility spikes

## Response Format
Analyze the data and respond with clear reasoning:

\`\`\`json
{
  "action": "BUY|SELL|HOLD|CLOSE",
  "confidence": "HIGH|MEDIUM|LOW",
  "reasoning": "Brief explanation of key factors",
  "entry_price": 0.0,
  "stop_loss_pct": 1.5,
  "take_profit_pct": 3.0,
  "position_size_pct": 5.0
}
\`\`\`

Remember: It's better to miss opportunities than to force trades. Wait for high-quality setups.`

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
    indicators: ["RSI", "ADX", "CHOP", "KAMA"] as string[],
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

    if (!formData.name.trim()) {
      setError("Agent name is required")
      return
    }
    if (!formData.modelId) {
      setError("Please select an AI model")
      return
    }
    if (!formData.exchangeId) {
      setError("Please select an exchange")
      return
    }
    if (formData.indicators.length === 0) {
      setError("Please select at least one technical indicator")
      return
    }

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
        indicators: ["RSI", "ADX", "CHOP", "KAMA"],
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
      <DialogContent className="sm:max-w-[700px] max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Create Trading Agent</DialogTitle>
          <DialogDescription>Configure a new AI-powered trading agent with custom strategy.</DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit}>
          <div className="grid gap-5 py-4">
            {error && (
              <Alert variant="destructive">
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            <div className="grid gap-2">
              <Label htmlFor="name">Agent Name *</Label>
              <Input
                id="name"
                placeholder="e.g., BTC Trend Follower"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                required
                disabled={isCreatingAgent}
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="grid gap-2">
                <Label htmlFor="model">AI Model *</Label>
                <Select
                  value={formData.modelId}
                  onValueChange={(value) => setFormData({ ...formData, modelId: value })}
                  disabled={isCreatingAgent}
                  required
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select model" />
                  </SelectTrigger>
                  <SelectContent>
                    {models.length === 0 ? (
                      <div className="px-2 py-6 text-center text-sm text-muted-foreground">No models available</div>
                    ) : (
                      models.map((model) => (
                        <SelectItem key={model.id} value={model.id}>
                          {model.name}
                        </SelectItem>
                      ))
                    )}
                  </SelectContent>
                </Select>
              </div>

              <div className="grid gap-2">
                <Label htmlFor="exchange">Exchange *</Label>
                <Select
                  value={formData.exchangeId}
                  onValueChange={(value) => setFormData({ ...formData, exchangeId: value })}
                  disabled={isCreatingAgent}
                  required
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select exchange" />
                  </SelectTrigger>
                  <SelectContent>
                    {exchanges.length === 0 ? (
                      <div className="px-2 py-6 text-center text-sm text-muted-foreground">No exchanges available</div>
                    ) : (
                      exchanges.map((exchange) => (
                        <SelectItem key={exchange.id} value={exchange.id}>
                          {exchange.name}
                        </SelectItem>
                      ))
                    )}
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
                  onChange={(e) => setFormData({ ...formData, symbol: e.target.value.toUpperCase() })}
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
              <Label>Technical Indicators *</Label>
              <div className="flex flex-wrap gap-2">
                {availableIndicators.map((indicator) => (
                  <Badge
                    key={indicator}
                    variant={formData.indicators.includes(indicator) ? "default" : "outline"}
                    className="cursor-pointer transition-all hover:scale-105"
                    onClick={() => !isCreatingAgent && toggleIndicator(indicator)}
                  >
                    {indicator}
                    {formData.indicators.includes(indicator) && <X className="ml-1 h-3 w-3" />}
                  </Badge>
                ))}
              </div>
              <p className="text-xs text-muted-foreground">Selected: {formData.indicators.length} indicators</p>
            </div>

            <div className="grid gap-2">
              <Label htmlFor="prompt">System Prompt</Label>
              <Textarea
                id="prompt"
                rows={10}
                className="font-mono text-xs leading-relaxed"
                value={formData.prompt}
                onChange={(e) => setFormData({ ...formData, prompt: e.target.value })}
                required
                disabled={isCreatingAgent}
              />
              <p className="text-xs text-muted-foreground">
                Define your agent's trading strategy and decision-making logic
              </p>
            </div>
          </div>
          <DialogFooter className="gap-2">
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
