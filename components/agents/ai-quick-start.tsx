"use client"

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Brain, TrendingUp, Activity, History, X } from "lucide-react"
import { useState } from "react"

interface AIQuickStartProps {
  onClose?: () => void
}

export function AIQuickStart({ onClose }: AIQuickStartProps) {
  const [dismissed, setDismissed] = useState(false)

  if (dismissed) return null

  const handleDismiss = () => {
    setDismissed(true)
    onClose?.()
  }

  return (
    <Card className="border-primary/50 bg-primary/5">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-2">
            <Brain className="h-5 w-5 text-primary" />
            <div>
              <CardTitle className="text-base">AI Trading Agent Active</CardTitle>
              <CardDescription>Get intelligent trading recommendations powered by AI</CardDescription>
            </div>
          </div>
          <Button variant="ghost" size="icon" className="h-6 w-6" onClick={handleDismiss}>
            <X className="h-4 w-4" />
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid gap-3 sm:grid-cols-3">
          <div className="flex gap-3 p-3 rounded-lg bg-background/50 border border-border">
            <div className="shrink-0">
              <div className="h-8 w-8 rounded-full bg-primary/10 flex items-center justify-center">
                <Activity className="h-4 w-4 text-primary" />
              </div>
            </div>
            <div className="space-y-1">
              <div className="text-sm font-medium">Real-time Analysis</div>
              <div className="text-xs text-muted-foreground">
                10+ technical indicators calculated live
              </div>
            </div>
          </div>

          <div className="flex gap-3 p-3 rounded-lg bg-background/50 border border-border">
            <div className="shrink-0">
              <div className="h-8 w-8 rounded-full bg-primary/10 flex items-center justify-center">
                <TrendingUp className="h-4 w-4 text-primary" />
              </div>
            </div>
            <div className="space-y-1">
              <div className="text-sm font-medium">AI Decisions</div>
              <div className="text-xs text-muted-foreground">
                LONG, SHORT, or HOLD recommendations
              </div>
            </div>
          </div>

          <div className="flex gap-3 p-3 rounded-lg bg-background/50 border border-border">
            <div className="shrink-0">
              <div className="h-8 w-8 rounded-full bg-primary/10 flex items-center justify-center">
                <History className="h-4 w-4 text-primary" />
              </div>
            </div>
            <div className="space-y-1">
              <div className="text-sm font-medium">Action History</div>
              <div className="text-xs text-muted-foreground">
                Track all signals and performance
              </div>
            </div>
          </div>
        </div>

        <div className="flex items-center justify-between pt-2">
          <div className="flex items-center gap-2">
            <Badge variant="default" className="text-xs">
              GPT-4o-mini
            </Badge>
            <span className="text-xs text-muted-foreground">
              Powered by Vercel AI SDK
            </span>
          </div>
          <Button variant="link" size="sm" className="h-auto p-0 text-xs" asChild>
            <a href="#" onClick={(e) => e.preventDefault()}>
              Learn more →
            </a>
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
