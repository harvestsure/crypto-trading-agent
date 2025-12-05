"use client"

import type React from "react"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
  Wrench,
  ShoppingCart,
  Target,
  ShieldAlert,
  XCircle,
  Search,
  Wallet,
  TrendingUp,
  CheckCircle2,
  AlertCircle,
  Loader2,
} from "lucide-react"
import { cn } from "@/lib/utils"
import type { ToolCall } from "@/lib/types"

interface ToolOperationsProps {
  toolCalls: ToolCall[]
}

const toolIcons: Record<string, React.ReactNode> = {
  create_order: <ShoppingCart className="h-4 w-4" />,
  set_stop_loss: <ShieldAlert className="h-4 w-4" />,
  set_take_profit: <Target className="h-4 w-4" />,
  close_position: <XCircle className="h-4 w-4" />,
  get_positions: <Search className="h-4 w-4" />,
  get_balance: <Wallet className="h-4 w-4" />,
  get_market_data: <TrendingUp className="h-4 w-4" />,
}

export function ToolOperations({ toolCalls }: ToolOperationsProps) {
  const getStatusBadge = (status: string) => {
    switch (status) {
      case "success":
        return (
          <Badge variant="default" className="bg-success text-success-foreground">
            Success
          </Badge>
        )
      case "error":
        return <Badge variant="destructive">Failed</Badge>
      case "pending":
        return <Badge variant="secondary">Pending</Badge>
      default:
        return <Badge variant="secondary">{status}</Badge>
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "success":
        return <CheckCircle2 className="h-4 w-4 text-success" />
      case "error":
        return <AlertCircle className="h-4 w-4 text-destructive" />
      case "pending":
        return <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
      default:
        return null
    }
  }

  return (
    <Card className="h-full">
      <CardHeader className="pb-2">
        <CardTitle className="text-base flex items-center justify-between">
          <span className="flex items-center gap-2">
            <Wrench className="h-4 w-4" />
            Tool Operations
          </span>
          <Badge variant="secondary">{toolCalls.length}</Badge>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <ScrollArea className="h-[400px] pr-4">
          <div className="space-y-3">
            {toolCalls.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-8">No tool operations yet</p>
            ) : (
              toolCalls.map((tool) => (
                <div key={tool.id} className="rounded-lg border border-border p-3 space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-chart-3/10">
                        {toolIcons[tool.name] || <Wrench className="h-4 w-4 text-chart-3" />}
                      </div>
                      <div>
                        <p className="text-sm font-medium text-foreground font-mono">{tool.name}</p>
                        <p className="text-xs text-muted-foreground">{new Date(tool.timestamp).toLocaleTimeString()}</p>
                      </div>
                    </div>
                    {getStatusIcon(tool.status)}
                  </div>

                  <div className="rounded bg-secondary/50 p-2">
                    <p className="text-xs text-muted-foreground mb-1">Arguments:</p>
                    <pre className="text-xs text-foreground overflow-x-auto font-mono">
                      {JSON.stringify(tool.arguments, null, 2)}
                    </pre>
                  </div>

                  {tool.result && (
                    <div
                      className={cn(
                        "rounded p-2 text-xs",
                        tool.status === "success" ? "bg-success/10" : "bg-destructive/10",
                      )}
                    >
                      <p className="text-muted-foreground mb-1">Result:</p>
                      <p className={cn("font-mono", tool.status === "success" ? "text-success" : "text-destructive")}>
                        {tool.result}
                      </p>
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  )
}
