"use client"

import type React from "react"
import { useState, useEffect } from "react"
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
import type { TradingAgent } from "@/lib/types"

interface EditAgentModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  agent: TradingAgent | null
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

export function EditAgentModal({ open, onOpenChange, agent, onSuccess }: EditAgentModalProps) {
  const { models = [] } = useModels()
  const { exchanges = [] } = useExchanges()
  const agents = useAppStore((state) => state.agents)

  const [formData, setFormData] = useState({
    name: "",
    modelId: "",
    exchangeId: "",
    symbols: "",
    timeframe: "1h",
    indicators: [] as string[],
    prompt: "",
  })
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState("")

  // Initialize form with agent data when modal opens
  useEffect(() => {
    if (agent && open) {
      setFormData({
        name: agent.name || "",
        modelId: agent.modelId || "",
        exchangeId: agent.exchangeId || "",
        symbols: Array.isArray(agent.symbols) ? agent.symbols.join(", ") : "",
        timeframe: agent.timeframe || "1h",
        indicators: (agent.indicators as string[]) || [],
        prompt: (agent as any).prompt || "",
      })
      setError("")
    }
  }, [agent, open])

  const handleSave = async () => {
    if (!agent || !formData.name.trim()) {
      setError("Agent name is required")
      return
    }

    setIsLoading(true)
    setError("")

    try {
      // Update local store
      useAppStore.setState((state) => ({
        agents: state.agents.map((a) =>
          a.id === agent.id
            ? {
                ...a,
                name: formData.name,
                modelId: formData.modelId,
                exchangeId: formData.exchangeId,
                symbols: formData.symbols
                  .split(",")
                  .map((s) => s.trim())
                  .filter((s) => s),
                timeframe: formData.timeframe,
                indicators: formData.indicators,
                prompt: formData.prompt,
              }
            : a
        ),
      }))

      setIsLoading(false)
      onOpenChange(false)
      onSuccess?.()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save agent")
      setIsLoading(false)
    }
  }

  const toggleIndicator = (indicator: string) => {
    setFormData((prev) => ({
      ...prev,
      indicators: prev.indicators.includes(indicator)
        ? prev.indicators.filter((i) => i !== indicator)
        : [...prev.indicators, indicator],
    }))
  }

  if (!agent) return null

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Edit Agent Settings</DialogTitle>
          <DialogDescription>Modify the configuration for this trading agent</DialogDescription>
        </DialogHeader>

        <div className="space-y-6">
          {error && (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {/* Agent Name */}
          <div className="space-y-2">
            <Label htmlFor="name">Agent Name *</Label>
            <Input
              id="name"
              placeholder="e.g., BTC Trading Bot"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            />
          </div>

          {/* Model & Exchange */}
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="model">AI Model</Label>
              <Select value={formData.modelId} onValueChange={(value) => setFormData({ ...formData, modelId: value })}>
                <SelectTrigger id="model">
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

            <div className="space-y-2">
              <Label htmlFor="exchange">Exchange</Label>
              <Select value={formData.exchangeId} onValueChange={(value) => setFormData({ ...formData, exchangeId: value })}>
                <SelectTrigger id="exchange">
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

          {/* Trading Pairs & Timeframe */}
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="symbols">Trading Pairs</Label>
              <Input
                id="symbols"
                placeholder="e.g., BTC/USDT, ETH/USDT"
                value={formData.symbols}
                onChange={(e) => setFormData({ ...formData, symbols: e.target.value })}
              />
              <p className="text-xs text-muted-foreground">Separate multiple pairs with commas</p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="timeframe">Timeframe</Label>
              <Select value={formData.timeframe} onValueChange={(value) => setFormData({ ...formData, timeframe: value })}>
                <SelectTrigger id="timeframe">
                  <SelectValue placeholder="Select timeframe" />
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

          {/* Indicators */}
          <div className="space-y-2">
            <Label>Technical Indicators</Label>
            <div className="flex flex-wrap gap-2 p-3 border border-input rounded-md bg-background">
              {availableIndicators.map((indicator) => (
                <Badge
                  key={indicator}
                  variant={formData.indicators.includes(indicator) ? "default" : "outline"}
                  className="cursor-pointer"
                  onClick={() => toggleIndicator(indicator)}
                >
                  {indicator}
                </Badge>
              ))}
            </div>
          </div>

          {/* System Prompt */}
          <div className="space-y-2">
            <Label htmlFor="prompt">System Prompt</Label>
            <Textarea
              id="prompt"
              placeholder="Enter the system prompt for this agent"
              value={formData.prompt}
              onChange={(e) => setFormData({ ...formData, prompt: e.target.value })}
              rows={8}
              className="font-mono text-xs"
            />
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={isLoading}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={isLoading}>
            {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Save Changes
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
