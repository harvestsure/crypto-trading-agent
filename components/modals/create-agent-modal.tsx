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
import { X, Loader2, AlertCircle, Bot, Sparkles } from "lucide-react"
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

${"```json"}
{
  "action": "BUY|SELL|HOLD|CLOSE",
  "confidence": "HIGH|MEDIUM|LOW",
  "reasoning": "Brief explanation of key factors",
  "entry_price": 0.0,
  "stop_loss_pct": 1.5,
  "take_profit_pct": 3.0,
  "position_size_pct": 5.0
}
${"```"}

Remember: It's better to miss opportunities than to force trades. Wait for high-quality setups.`

export function CreateAgentModal({ open, onOpenChange, onSuccess }: CreateAgentModalProps) {
  const { models } = useModels()
  const { exchanges } = useExchanges()
  const { createAgent, isCreatingAgent } = useAppStore()
  const [error, setError] = useState<string | null>(null)
  const [currentSymbol, setCurrentSymbol] = useState("")
  const [formData, setFormData] = useState({
    name: "",
    modelId: "",
    exchangeId: "",
    symbols: ["BTC/USDT"],
    timeframe: "1m",
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
      symbols: formData.symbols,
      timeframe: formData.timeframe,
      indicators: formData.indicators,
      prompt: formData.prompt,
    })

    if (result.success) {
      setFormData({
        name: "",
        modelId: "",
        exchangeId: "",
        symbols: ["BTC/USDT"],
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

  const addSymbols = () => {
    if (!currentSymbol.trim()) return
    const entries = currentSymbol
      .split(",")
      .map((s) => s.trim().toUpperCase())
      .filter(Boolean)
    setFormData((prev) => ({
      ...prev,
      symbols: Array.from(new Set([...prev.symbols, ...entries])),
    }))
    setCurrentSymbol("")
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl max-h-[90vh] overflow-hidden flex flex-col p-0">
        {/* Header */}
        <DialogHeader className="px-6 pt-6 pb-4 border-b border-border shrink-0">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
              <Bot className="h-5 w-5 text-primary" />
            </div>
            <div>
              <DialogTitle className="text-lg font-semibold">Create Trading Agent</DialogTitle>
              <DialogDescription className="text-sm text-muted-foreground">
                Configure an AI-powered trading agent with custom strategy
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>

        {/* Scrollable Content */}
        <form onSubmit={handleSubmit} className="flex flex-col flex-1 overflow-hidden">
          <div className="flex-1 overflow-y-auto px-6 py-5">
            <div className="space-y-6">
              {/* Error Alert */}
              {error && (
                <Alert variant="destructive" className="border-destructive/50 bg-destructive/10">
                  <AlertCircle className="h-4 w-4" />
                  <AlertDescription>{error}</AlertDescription>
                </Alert>
              )}

              {/* Agent Name */}
              <div className="space-y-2">
                <Label htmlFor="name" className="text-sm font-medium">
                  Agent Name <span className="text-destructive">*</span>
                </Label>
                <Input
                  id="name"
                  placeholder="e.g., BTC Trend Follower"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  required
                  disabled={isCreatingAgent}
                  className="h-10"
                />
              </div>

              {/* AI Model & Exchange - Two Columns */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="model" className="text-sm font-medium">
                    AI Model <span className="text-destructive">*</span>
                  </Label>
                  <Select
                    value={formData.modelId}
                    onValueChange={(value) => setFormData({ ...formData, modelId: value })}
                    disabled={isCreatingAgent}
                    required
                  >
                    <SelectTrigger className="h-10 w-full">
                      <SelectValue placeholder="Select model" />
                    </SelectTrigger>
                    <SelectContent>
                      {models.length === 0 ? (
                        <div className="px-2 py-4 text-center text-sm text-muted-foreground">No models available</div>
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

                <div className="space-y-2">
                  <Label htmlFor="exchange" className="text-sm font-medium">
                    Exchange <span className="text-destructive">*</span>
                  </Label>
                  <Select
                    value={formData.exchangeId}
                    onValueChange={(value) => setFormData({ ...formData, exchangeId: value })}
                    disabled={isCreatingAgent}
                    required
                  >
                    <SelectTrigger className="h-10 w-full">
                      <SelectValue placeholder="Select exchange" />
                    </SelectTrigger>
                    <SelectContent>
                      {exchanges.length === 0 ? (
                        <div className="px-2 py-4 text-center text-sm text-muted-foreground">
                          No exchanges available
                        </div>
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

              {/* Timeframe - Two Columns */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {/* Timeframe */}
                <div className="space-y-2">
                  <Label htmlFor="timeframe" className="text-sm font-medium">
                    Timeframe
                  </Label>
                  <Select
                    value={formData.timeframe}
                    onValueChange={(value: "1m" | "5m" | "15m" | "30m" | "1h" | "4h" | "1d") =>
                      setFormData({ ...formData, timeframe: value })
                    }
                    disabled={isCreatingAgent}
                  >
                    <SelectTrigger className="h-10 w-full">
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
              
              {/* Trading Pairs - Two Columns */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {/* Trading Pairs */}
                <div className="space-y-2">
                  <Label htmlFor="symbols" className="text-sm font-medium">
                    Trading Pairs
                  </Label>
                  <div className="space-y-3">
                    {/* Selected Symbols */}
                    {formData.symbols.length > 0 && (
                      <div className="flex flex-wrap gap-1.5">
                        {formData.symbols.map((sym) => (
                          <Badge key={sym} variant="secondary" className="h-7 pl-2.5 pr-1.5 gap-1 font-medium">
                            {sym}
                            <button
                              type="button"
                              onClick={() =>
                                !isCreatingAgent &&
                                setFormData((prev) => ({
                                  ...prev,
                                  symbols: prev.symbols.filter((s) => s !== sym),
                                }))
                              }
                              className="ml-0.5 rounded-full p-0.5 hover:bg-muted-foreground/20 transition-colors"
                              disabled={isCreatingAgent}
                            >
                              <X className="h-3 w-3" />
                            </button>
                          </Badge>
                        ))}
                      </div>
                    )}
                    {/* Input Field */}
                    <div className="flex gap-2">
                      <Input
                        id="symbols"
                        placeholder="e.g., ETH/USDT"
                        value={currentSymbol}
                        onChange={(e) => setCurrentSymbol(e.target.value.toUpperCase())}
                        onKeyDown={(e) => {
                          if ((e.key === "Enter" || e.key === ",") && currentSymbol.trim()) {
                            e.preventDefault()
                            addSymbols()
                          }
                        }}
                        disabled={isCreatingAgent}
                        className="h-10 flex-1"
                      />
                      <Button
                        type="button"
                        variant="outline"
                        onClick={addSymbols}
                        disabled={isCreatingAgent || !currentSymbol.trim()}
                        className="h-10 px-4 shrink-0 bg-transparent"
                      >
                        Add
                      </Button>
                    </div>
                  </div>
                </div>
              </div>

              {/* Technical Indicators */}
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <Label className="text-sm font-medium">
                    Technical Indicators <span className="text-destructive">*</span>
                  </Label>
                  <span className="text-xs text-muted-foreground">{formData.indicators.length} selected</span>
                </div>
                <div className="flex flex-wrap gap-2">
                  {availableIndicators.map((indicator) => {
                    const isSelected = formData.indicators.includes(indicator)
                    return (
                      <Badge
                        key={indicator}
                        variant={isSelected ? "default" : "outline"}
                        className={`cursor-pointer h-8 px-3 font-medium transition-all hover:scale-105 ${
                          isSelected
                            ? "bg-primary text-primary-foreground"
                            : "hover:bg-accent hover:text-accent-foreground"
                        }`}
                        onClick={() => !isCreatingAgent && toggleIndicator(indicator)}
                      >
                        {indicator}
                        {isSelected && <X className="ml-1.5 h-3 w-3" />}
                      </Badge>
                    )
                  })}
                </div>
              </div>

              {/* System Prompt */}
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <Sparkles className="h-4 w-4 text-muted-foreground" />
                  <Label htmlFor="prompt" className="text-sm font-medium">
                    System Prompt
                  </Label>
                </div>
                <Textarea
                  id="prompt"
                  rows={8}
                  className="font-mono text-xs leading-relaxed resize-none"
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
          </div>

          {/* Footer */}
          <DialogFooter className="px-6 py-4 border-t border-border shrink-0 gap-2 sm:gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={isCreatingAgent}
              className="h-10"
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={!formData.modelId || !formData.exchangeId || isCreatingAgent}
              className="h-10 min-w-[120px]"
            >
              {isCreatingAgent ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Creating...
                </>
              ) : (
                "Create Agent"
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
