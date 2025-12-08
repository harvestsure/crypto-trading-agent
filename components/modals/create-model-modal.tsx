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
import { Loader2 } from "lucide-react"

interface CreateModelModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSuccess?: () => void // Added onSuccess callback for refetching
}

const providers = [
  { value: "openai", label: "OpenAI", models: ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"] },
  { value: "anthropic", label: "Anthropic", models: ["claude-3-5-sonnet-20241022", "claude-3-opus-20240229"] },
  { value: "deepseek", label: "DeepSeek", models: ["deepseek-chat", "deepseek-reasoner"] },
  { value: "custom", label: "Custom", models: [] },
]

export function CreateModelModal({ open, onOpenChange, onSuccess }: CreateModelModalProps) {
  const { createModel, isCreatingModel } = useAppStore()
  const [error, setError] = useState<string | null>(null)
  const [formData, setFormData] = useState({
    name: "",
    provider: "openai" as const,
    apiKey: "",
    baseUrl: "",
    model: "gpt-4o",
  })

  const selectedProvider = providers.find((p) => p.value === formData.provider)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    const result = await createModel({
      name: formData.name,
      provider: formData.provider,
      apiKey: formData.apiKey,
      baseUrl: formData.baseUrl || undefined,
      model: formData.model,
    })

    if (result.success) {
      setFormData({ name: "", provider: "openai", apiKey: "", baseUrl: "", model: "gpt-4o" })
      onOpenChange(false)
      onSuccess?.()
    } else {
      setError(result.error || "Failed to create model")
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>Create AI Model</DialogTitle>
          <DialogDescription>Configure a new AI model for your trading agents.</DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit}>
          <div className="grid gap-4 py-4">
            {error && <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">{error}</div>}

            <div className="grid gap-2">
              <Label htmlFor="name">Name</Label>
              <Input
                id="name"
                placeholder="My GPT-4 Model"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                required
                disabled={isCreatingModel}
              />
            </div>

            <div className="grid gap-2">
              <Label htmlFor="provider">Provider</Label>
              <Select
                value={formData.provider}
                onValueChange={(value: "openai" | "anthropic" | "deepseek" | "custom") =>
                  setFormData({
                    ...formData,
                    provider: value,
                    model: providers.find((p) => p.value === value)?.models[0] || "",
                  })
                }
                disabled={isCreatingModel}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {providers.map((provider) => (
                    <SelectItem key={provider.value} value={provider.value}>
                      {provider.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="grid gap-2">
              <Label htmlFor="model">Model</Label>
              {formData.provider === "custom" ? (
                <Input
                  id="model"
                  placeholder="model-name"
                  value={formData.model}
                  onChange={(e) => setFormData({ ...formData, model: e.target.value })}
                  required
                  disabled={isCreatingModel}
                />
              ) : (
                <Select
                  value={formData.model}
                  onValueChange={(value) => setFormData({ ...formData, model: value })}
                  disabled={isCreatingModel}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {selectedProvider?.models.map((model) => (
                      <SelectItem key={model} value={model}>
                        {model}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            </div>

            <div className="grid gap-2">
              <Label htmlFor="apiKey">API Key</Label>
              <Input
                id="apiKey"
                type="password"
                placeholder="sk-..."
                value={formData.apiKey}
                onChange={(e) => setFormData({ ...formData, apiKey: e.target.value })}
                required
                disabled={isCreatingModel}
              />
            </div>

            {formData.provider === "custom" && (
              <div className="grid gap-2">
                <Label htmlFor="baseUrl">Base URL</Label>
                <Input
                  id="baseUrl"
                  placeholder="https://api.example.com/v1"
                  value={formData.baseUrl}
                  onChange={(e) => setFormData({ ...formData, baseUrl: e.target.value })}
                  disabled={isCreatingModel}
                />
              </div>
            )}
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={isCreatingModel}>
              Cancel
            </Button>
            <Button type="submit" disabled={isCreatingModel}>
              {isCreatingModel && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Create Model
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
