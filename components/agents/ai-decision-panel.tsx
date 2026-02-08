"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Progress } from "@/components/ui/progress"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { cn } from "@/lib/utils"
import {
  TrendingUp,
  TrendingDown,
  Minus,
  Target,
  Shield,
  Brain,
  Zap,
  RefreshCw,
  AlertTriangle,
} from "lucide-react"
import type { TradingDecision } from "@/hooks/use-ai-trading"

interface AIDecisionPanelProps {
  decision?: TradingDecision | null
  isAnalyzing?: boolean
  onAnalyze?: () => void
  lastUpdateTime?: number
}

export function AIDecisionPanel({
  decision,
  isAnalyzing = false,
  onAnalyze,
  lastUpdateTime,
}: AIDecisionPanelProps) {
  const getActionIcon = (action: string) => {
    switch (action) {
      case "LONG":
        return <TrendingUp className="h-4 w-4" />
      case "SHORT":
        return <TrendingDown className="h-4 w-4" />
      case "CLOSE_LONG":
      case "CLOSE_SHORT":
        return <Target className="h-4 w-4" />
      default:
        return <Minus className="h-4 w-4" />
    }
  }

  const getActionColor = (action: string) => {
    switch (action) {
      case "LONG":
        return "text-success"
      case "SHORT":
        return "text-destructive"
      case "CLOSE_LONG":
      case "CLOSE_SHORT":
        return "text-warning"
      default:
        return "text-muted-foreground"
    }
  }

  const getActionBadgeVariant = (action: string): "default" | "secondary" | "outline" => {
    switch (action) {
      case "LONG":
      case "SHORT":
        return "default"
      case "CLOSE_LONG":
      case "CLOSE_SHORT":
        return "secondary"
      default:
        return "outline"
    }
  }

  const getConfidenceLevel = (confidence: number): { label: string; color: string } => {
    if (confidence >= 0.8) return { label: "Very High", color: "text-success" }
    if (confidence >= 0.6) return { label: "High", color: "text-success" }
    if (confidence >= 0.4) return { label: "Moderate", color: "text-warning" }
    if (confidence >= 0.2) return { label: "Low", color: "text-destructive" }
    return { label: "Very Low", color: "text-destructive" }
  }

  const formatTime = (timestamp: number) => {
    const date = new Date(timestamp)
    return date.toLocaleTimeString()
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base flex items-center justify-between">
          <span className="flex items-center gap-2">
            <Brain className="h-4 w-4 text-primary" />
            AI Trading Decision
          </span>
          {onAnalyze && (
            <Button
              variant="ghost"
              size="sm"
              onClick={onAnalyze}
              disabled={isAnalyzing}
              className="h-8"
            >
              {isAnalyzing ? (
                <RefreshCw className="h-3 w-3 animate-spin" />
              ) : (
                <Zap className="h-3 w-3" />
              )}
              <span className="ml-2">{isAnalyzing ? "Analyzing..." : "Analyze"}</span>
            </Button>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {isAnalyzing && !decision && (
          <div className="flex flex-col items-center justify-center py-8 text-center space-y-3">
            <RefreshCw className="h-8 w-8 text-primary animate-spin" />
            <p className="text-sm text-muted-foreground">Analyzing market conditions...</p>
          </div>
        )}

        {!isAnalyzing && !decision && (
          <div className="flex flex-col items-center justify-center py-8 text-center space-y-3">
            <Brain className="h-8 w-8 text-muted-foreground" />
            <p className="text-sm text-muted-foreground">No analysis available</p>
            {onAnalyze && (
              <Button variant="outline" size="sm" onClick={onAnalyze}>
                <Zap className="mr-2 h-3 w-3" />
                Run Analysis
              </Button>
            )}
          </div>
        )}

        {decision && (
          <>
            {/* Action & Confidence */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">Recommended Action</span>
                <Badge variant={getActionBadgeVariant(decision.action)} className="gap-1">
                  {getActionIcon(decision.action)}
                  {decision.action.replace("_", " ")}
                </Badge>
              </div>

              <div className="space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">Confidence</span>
                  <span className={cn("font-semibold", getConfidenceLevel(decision.confidence).color)}>
                    {(decision.confidence * 100).toFixed(0)}%{" "}
                    <span className="text-xs">({getConfidenceLevel(decision.confidence).label})</span>
                  </span>
                </div>
                <Progress
                  value={decision.confidence * 100}
                  className={cn(
                    "h-2",
                    decision.confidence >= 0.6 && "[&>div]:bg-success",
                    decision.confidence < 0.4 && "[&>div]:bg-destructive",
                  )}
                />
              </div>
            </div>

            {/* Position Size */}
            {decision.positionSize && (
              <div className="flex items-center justify-between p-3 bg-muted rounded-lg">
                <span className="text-sm text-muted-foreground">Position Size</span>
                <span className="font-semibold">{decision.positionSize}%</span>
              </div>
            )}

            {/* Stop Loss & Take Profit */}
            {(decision.stopLoss || decision.takeProfit) && (
              <div className="grid grid-cols-2 gap-3">
                {decision.stopLoss && (
                  <div className="flex flex-col gap-1 p-3 bg-destructive/10 rounded-lg border border-destructive/20">
                    <div className="flex items-center gap-1 text-xs text-destructive">
                      <Shield className="h-3 w-3" />
                      <span>Stop Loss</span>
                    </div>
                    <span className="font-semibold text-sm">${decision.stopLoss.toLocaleString()}</span>
                  </div>
                )}
                {decision.takeProfit && (
                  <div className="flex flex-col gap-1 p-3 bg-success/10 rounded-lg border border-success/20">
                    <div className="flex items-center gap-1 text-xs text-success">
                      <Target className="h-3 w-3" />
                      <span>Take Profit</span>
                    </div>
                    <span className="font-semibold text-sm">
                      ${decision.takeProfit.toLocaleString()}
                    </span>
                  </div>
                )}
              </div>
            )}

            {/* Reasoning */}
            <Alert>
              <AlertTriangle className="h-4 w-4" />
              <AlertDescription className="text-sm leading-relaxed">
                {decision.reasoning}
              </AlertDescription>
            </Alert>

            {/* Last Update */}
            {lastUpdateTime && (
              <div className="text-xs text-muted-foreground text-center">
                Last updated: {formatTime(lastUpdateTime)}
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  )
}
