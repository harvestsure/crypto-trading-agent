"use client"

import type React from "react"
import { useState } from "react"
import { useAppStore } from "@/lib/store"
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
import { Switch } from "@/components/ui/switch"
import { Loader2 } from "lucide-react"

interface CreateExchangeModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSuccess?: () => void // Added onSuccess callback for refetching
}

const exchanges = [
  { value: "binance", label: "Binance", needsPassphrase: false },
  { value: "okx", label: "OKX", needsPassphrase: true },
  { value: "bybit", label: "Bybit", needsPassphrase: false },
  { value: "bitget", label: "Bitget", needsPassphrase: true },
  { value: "gate", label: "Gate.io", needsPassphrase: false },
]

export function CreateExchangeModal({ open, onOpenChange, onSuccess }: CreateExchangeModalProps) {
  const { createExchange, isCreatingExchange } = useAppStore()
  const [error, setError] = useState<string | null>(null)
  const [formData, setFormData] = useState({
    name: "",
    exchange: "binance" as const,
    apiKey: "",
    secretKey: "",
    passphrase: "",
    testnet: true,
  })

  const selectedExchange = exchanges.find((e) => e.value === formData.exchange)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    const result = await createExchange({
      name: formData.name,
      exchange: formData.exchange,
      apiKey: formData.apiKey,
      secretKey: formData.secretKey,
      passphrase: formData.passphrase || undefined,
      testnet: formData.testnet,
    })

    if (result.success) {
      setFormData({ name: "", exchange: "binance", apiKey: "", secretKey: "", passphrase: "", testnet: true })
      onOpenChange(false)
      onSuccess?.()
    } else {
      setError(result.error || "Failed to create exchange")
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>Add Exchange</DialogTitle>
          <DialogDescription>Connect your exchange account for automated trading.</DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit}>
          <div className="grid gap-4 py-4">
            {error && <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">{error}</div>}

            <div className="grid gap-2">
              <Label htmlFor="name">Name</Label>
              <Input
                id="name"
                placeholder="My Binance Account"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                required
                disabled={isCreatingExchange}
              />
            </div>

            <div className="grid gap-2">
              <Label htmlFor="exchange">Exchange</Label>
              <Select
                value={formData.exchange}
                onValueChange={(value: "binance" | "okx" | "bybit" | "bitget" | "gate") =>
                  setFormData({ ...formData, exchange: value })
                }
                disabled={isCreatingExchange}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {exchanges.map((exchange) => (
                    <SelectItem key={exchange.value} value={exchange.value}>
                      {exchange.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="grid gap-2">
              <Label htmlFor="apiKey">API Key</Label>
              <Input
                id="apiKey"
                type="password"
                placeholder="Enter your API key"
                value={formData.apiKey}
                onChange={(e) => setFormData({ ...formData, apiKey: e.target.value })}
                required
                disabled={isCreatingExchange}
              />
            </div>

            <div className="grid gap-2">
              <Label htmlFor="secretKey">Secret Key</Label>
              <Input
                id="secretKey"
                type="password"
                placeholder="Enter your secret key"
                value={formData.secretKey}
                onChange={(e) => setFormData({ ...formData, secretKey: e.target.value })}
                required
                disabled={isCreatingExchange}
              />
            </div>

            {selectedExchange?.needsPassphrase && (
              <div className="grid gap-2">
                <Label htmlFor="passphrase">Passphrase</Label>
                <Input
                  id="passphrase"
                  type="password"
                  placeholder="Enter your passphrase"
                  value={formData.passphrase}
                  onChange={(e) => setFormData({ ...formData, passphrase: e.target.value })}
                  required
                  disabled={isCreatingExchange}
                />
              </div>
            )}

            <div className="flex items-center justify-between rounded-lg border border-border p-4">
              <div>
                <Label htmlFor="testnet" className="font-medium">
                  Testnet Mode
                </Label>
                <p className="text-sm text-muted-foreground">Use testnet for paper trading</p>
              </div>
              <Switch
                id="testnet"
                checked={formData.testnet}
                onCheckedChange={(checked) => setFormData({ ...formData, testnet: checked })}
                disabled={isCreatingExchange}
              />
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={isCreatingExchange}>
              Cancel
            </Button>
            <Button type="submit" disabled={isCreatingExchange}>
              {isCreatingExchange && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Add Exchange
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
