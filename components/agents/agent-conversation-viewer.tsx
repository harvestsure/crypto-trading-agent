"use client"

import { useEffect, useRef } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  Bot,
  User,
  Wrench,
  RefreshCw,
  Zap,
  CheckCircle2,
  XCircle,
  Clock,
  MessageSquare,
  TrendingUp,
  TrendingDown,
  Minus,
  Signal,
} from "lucide-react"
import { cn } from "@/lib/utils"
import {
  useAgentConversations,
  useAgentToolCalls,
  useAgentSignals,
  useBackendStatus,
} from "@/hooks/use-agent-data"
import type { ConversationMessage, ToolCall } from "@/lib/types"

interface AgentConversationViewerProps {
  agentId: string
}

// ---- Action badge helpers ----
const ACTION_CONFIG: Record<string, { label: string; className: string; icon: React.ReactNode }> = {
  LONG: {
    label: "LONG",
    className: "bg-success/15 text-success border-success/30",
    icon: <TrendingUp className="h-3 w-3" />,
  },
  SHORT: {
    label: "SHORT",
    className: "bg-destructive/15 text-destructive border-destructive/30",
    icon: <TrendingDown className="h-3 w-3" />,
  },
  CLOSE: {
    label: "CLOSE",
    className: "bg-warning/15 text-warning border-warning/30",
    icon: <Minus className="h-3 w-3" />,
  },
  HOLD: {
    label: "HOLD",
    className: "bg-muted text-muted-foreground border-border",
    icon: <Minus className="h-3 w-3" />,
  },
  BUY: {
    label: "BUY",
    className: "bg-success/15 text-success border-success/30",
    icon: <TrendingUp className="h-3 w-3" />,
  },
  SELL: {
    label: "SELL",
    className: "bg-destructive/15 text-destructive border-destructive/30",
    icon: <TrendingDown className="h-3 w-3" />,
  },
}

function ActionBadge({ action }: { action: string }) {
  const cfg = ACTION_CONFIG[action?.toUpperCase()] ?? ACTION_CONFIG["HOLD"]
  return (
    <Badge variant="outline" className={cn("flex items-center gap-1 text-xs font-semibold px-2 py-0.5", cfg.className)}>
      {cfg.icon}
      {cfg.label}
    </Badge>
  )
}

// ---- Role styling ----
const ROLE_STYLE: Record<string, string> = {
  user: "bg-primary/5 border-primary/20",
  assistant: "bg-secondary border-border",
  system: "bg-warning/8 border-warning/20",
  tool: "bg-chart-3/8 border-chart-3/20",
}

function getRoleIcon(role: string) {
  switch (role) {
    case "user": return <User className="h-3.5 w-3.5 text-primary" />
    case "assistant": return <Bot className="h-3.5 w-3.5 text-success" />
    case "system": return <Zap className="h-3.5 w-3.5 text-warning" />
    case "tool": return <Wrench className="h-3.5 w-3.5 text-chart-3" />
    default: return <MessageSquare className="h-3.5 w-3.5 text-muted-foreground" />
  }
}

function formatTime(ts: Date | string | undefined) {
  if (!ts) return ""
  const d = ts instanceof Date ? ts : new Date(ts)
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })
}

// ---- Conversation Tab ----
function ConversationTab({ agentId, isConnected }: { agentId: string; isConnected: boolean }) {
  const { conversations, isLoading, refresh } = useAgentConversations(agentId, true)
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = scrollRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [conversations])

  return (
    <Card className="flex flex-col h-full border-0 shadow-none rounded-none">
      <CardHeader className="pb-2 flex flex-row items-center justify-between shrink-0 border-b px-4 pt-3">
        <CardTitle className="text-sm flex items-center gap-2">
          <MessageSquare className="h-4 w-4" />
          Conversation
        </CardTitle>
        <div className="flex items-center gap-2">
          <div className={cn("h-2 w-2 rounded-full", isConnected ? "bg-success" : "bg-destructive")} />
          <span className="text-xs text-muted-foreground">{isConnected ? "Live" : "Offline"}</span>
          <Button variant="ghost" size="sm" onClick={() => refresh()} disabled={isLoading} className="h-6 w-6 p-0">
            <RefreshCw className={cn("h-3 w-3", isLoading && "animate-spin")} />
          </Button>
        </div>
      </CardHeader>
      <CardContent className="flex-1 min-h-0 p-0">
        <ScrollArea className="h-full" ref={scrollRef}>
          <div className="space-y-2 p-3">
            {conversations.length === 0 && !isLoading && (
              <div className="flex flex-col items-center justify-center py-12 text-muted-foreground text-sm">
                <Bot className="h-8 w-8 mb-2 opacity-40" />
                No conversation yet
              </div>
            )}
            {conversations.map((msg: ConversationMessage) => (
              <div
                key={msg.id}
                className={cn(
                  "rounded-lg border p-3 space-y-1.5",
                  ROLE_STYLE[msg.role] ?? "bg-secondary border-border",
                )}
              >
                {/* Header */}
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5">
                    {getRoleIcon(msg.role)}
                    <span className="text-xs font-semibold capitalize text-foreground">{msg.role}</span>
                  </div>
                  <span className="text-xs text-muted-foreground">{formatTime(msg.timestamp)}</span>
                </div>

                {/* Content */}
                <p className="text-xs text-foreground leading-relaxed whitespace-pre-wrap break-words">
                  {msg.content}
                </p>

                {/* Inline tool call */}
                {msg.toolCall && (
                  <div className="rounded bg-background/60 border border-border p-2 space-y-1">
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-1.5">
                        <Wrench className="h-3 w-3 text-chart-3" />
                        <span className="text-xs font-mono text-chart-3 font-semibold">{msg.toolCall.name}</span>
                      </div>
                      {msg.toolCall.status === "pending" && <Clock className="h-3 w-3 text-muted-foreground" />}
                      {msg.toolCall.status === "success" && <CheckCircle2 className="h-3 w-3 text-success" />}
                      {msg.toolCall.status === "error" && <XCircle className="h-3 w-3 text-destructive" />}
                    </div>
                    <pre className="text-xs text-muted-foreground overflow-x-auto">
                      {JSON.stringify(msg.toolCall.arguments, null, 2)}
                    </pre>
                    {msg.toolCall.result && (
                      <p className="text-xs text-foreground pt-1 border-t border-border">
                        {msg.toolCall.result}
                      </p>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  )
}

// ---- Tool Calls Tab ----
function ToolCallsTab({ agentId }: { agentId: string }) {
  const { toolCalls, isLoading, refresh } = useAgentToolCalls(agentId, true)

  return (
    <Card className="flex flex-col h-full border-0 shadow-none rounded-none">
      <CardHeader className="pb-2 flex flex-row items-center justify-between shrink-0 border-b px-4 pt-3">
        <CardTitle className="text-sm flex items-center gap-2">
          <Wrench className="h-4 w-4" />
          Tool Calls
        </CardTitle>
        <Button variant="ghost" size="sm" onClick={() => refresh()} disabled={isLoading} className="h-6 w-6 p-0">
          <RefreshCw className={cn("h-3 w-3", isLoading && "animate-spin")} />
        </Button>
      </CardHeader>
      <CardContent className="flex-1 min-h-0 p-0">
        <ScrollArea className="h-full">
          <div className="space-y-2 p-3">
            {toolCalls.length === 0 && !isLoading && (
              <div className="flex flex-col items-center justify-center py-12 text-muted-foreground text-sm">
                <Wrench className="h-8 w-8 mb-2 opacity-40" />
                No tool calls yet
              </div>
            )}
            {toolCalls.map((tc: ToolCall) => (
              <div
                key={tc.id}
                className="rounded-lg border border-chart-3/20 bg-chart-3/5 p-3 space-y-2"
              >
                {/* Name + status */}
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-1.5">
                    <Wrench className="h-3.5 w-3.5 text-chart-3" />
                    <span className="text-xs font-semibold font-mono text-foreground">{tc.name}</span>
                  </div>
                  <div className="flex items-center gap-1">
                    {tc.status === "success" && (
                      <span className="flex items-center gap-0.5 text-success text-xs">
                        <CheckCircle2 className="h-3 w-3" /> Success
                      </span>
                    )}
                    {tc.status === "error" && (
                      <span className="flex items-center gap-0.5 text-destructive text-xs">
                        <XCircle className="h-3 w-3" /> Failed
                      </span>
                    )}
                    {tc.status === "pending" && (
                      <span className="flex items-center gap-0.5 text-muted-foreground text-xs">
                        <Clock className="h-3 w-3" /> Pending
                      </span>
                    )}
                  </div>
                </div>

                {/* Arguments */}
                <pre className="text-xs text-muted-foreground bg-background/60 rounded p-2 overflow-x-auto border border-border">
                  {JSON.stringify(tc.arguments, null, 2)}
                </pre>

                {/* Result */}
                {tc.result && (
                  <div className="text-xs bg-success/10 rounded p-2 border border-success/20 text-foreground">
                    {tc.result}
                  </div>
                )}

                <p className="text-xs text-muted-foreground text-right">{formatTime(tc.timestamp)}</p>
              </div>
            ))}
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  )
}

// ---- Signals Tab ----
function SignalsTab({ agentId }: { agentId: string }) {
  const { signals, isLoading, refresh } = useAgentSignals(agentId, true)

  return (
    <Card className="flex flex-col h-full border-0 shadow-none rounded-none">
      <CardHeader className="pb-2 flex flex-row items-center justify-between shrink-0 border-b px-4 pt-3">
        <CardTitle className="text-sm flex items-center gap-2">
          <Signal className="h-4 w-4" />
          Signals
        </CardTitle>
        <Button variant="ghost" size="sm" onClick={() => refresh()} disabled={isLoading} className="h-6 w-6 p-0">
          <RefreshCw className={cn("h-3 w-3", isLoading && "animate-spin")} />
        </Button>
      </CardHeader>
      <CardContent className="flex-1 min-h-0 p-0">
        <ScrollArea className="h-full">
          <div className="space-y-2 p-3">
            {signals.length === 0 && !isLoading && (
              <div className="flex flex-col items-center justify-center py-12 text-muted-foreground text-sm">
                <Signal className="h-8 w-8 mb-2 opacity-40" />
                No signals yet
              </div>
            )}
            {signals.map((signal: any) => {
              const snapshot = signal.indicators_snapshot ?? {}
              const action = (signal.action ?? "HOLD").toUpperCase()
              return (
                <div
                  key={signal.id}
                  className={cn(
                    "rounded-lg border p-3 space-y-2",
                    action === "LONG" ? "bg-success/8 border-success/20" :
                    action === "SHORT" ? "bg-destructive/8 border-destructive/20" :
                    "bg-muted border-border",
                  )}
                >
                  {/* Action + symbol */}
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <ActionBadge action={action} />
                      {snapshot.symbol && (
                        <span className="text-xs font-mono text-muted-foreground">{snapshot.symbol}</span>
                      )}
                    </div>
                    <span className="text-xs text-muted-foreground">{formatTime(signal.timestamp)}</span>
                  </div>

                  {/* Reason */}
                  {signal.reason && (
                    <p className="text-xs text-foreground leading-relaxed">{signal.reason}</p>
                  )}

                  {/* Position snapshot */}
                  {(snapshot.price || signal.take_profit || signal.stop_loss || snapshot.amount) && (
                    <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
                      {snapshot.price && (
                        <div>
                          <span className="text-muted-foreground">Price: </span>
                          <span className="font-mono">${Number(snapshot.price).toLocaleString()}</span>
                        </div>
                      )}
                      {snapshot.amount && (
                        <div>
                          <span className="text-muted-foreground">Size: </span>
                          <span className="font-mono">{snapshot.amount}</span>
                        </div>
                      )}
                      {signal.take_profit && (
                        <div>
                          <span className="text-success">TP: </span>
                          <span className="font-mono text-success">${Number(signal.take_profit).toLocaleString()}</span>
                        </div>
                      )}
                      {signal.stop_loss && (
                        <div>
                          <span className="text-destructive">SL: </span>
                          <span className="font-mono text-destructive">${Number(signal.stop_loss).toLocaleString()}</span>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Confidence */}
                  {signal.confidence != null && (
                    <div className="flex items-center gap-2">
                      <div className="flex-1 h-1.5 bg-border rounded-full overflow-hidden">
                        <div
                          className={cn(
                            "h-full rounded-full",
                            action === "LONG" ? "bg-success" :
                            action === "SHORT" ? "bg-destructive" : "bg-muted-foreground",
                          )}
                          style={{ width: `${Math.min(100, signal.confidence * 100)}%` }}
                        />
                      </div>
                      <span className="text-xs text-muted-foreground shrink-0">
                        {(signal.confidence * 100).toFixed(0)}%
                      </span>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  )
}

// ---- Main Component ----
export function AgentConversationViewer({ agentId }: AgentConversationViewerProps) {
  const { isConnected } = useBackendStatus()
  const { conversations } = useAgentConversations(agentId, true)
  const { toolCalls } = useAgentToolCalls(agentId, true)
  const { signals } = useAgentSignals(agentId, true)

  return (
    <Card className="flex flex-col h-full overflow-hidden">
      <Tabs defaultValue="conversations" className="flex flex-col h-full">
        <div className="border-b px-4 pt-3 pb-0 shrink-0">
          <h3 className="text-sm font-semibold mb-2 flex items-center gap-2">
            <Bot className="h-4 w-4" />
            AI Activity
          </h3>
          <TabsList className="grid w-full grid-cols-3 h-8">
            <TabsTrigger value="conversations" className="text-xs">
              Chat ({conversations.length})
            </TabsTrigger>
            <TabsTrigger value="tools" className="text-xs">
              Tools ({toolCalls.length})
            </TabsTrigger>
            <TabsTrigger value="signals" className="text-xs">
              Signals ({signals.length})
            </TabsTrigger>
          </TabsList>
        </div>

        <TabsContent value="conversations" className="flex-1 mt-0 overflow-hidden data-[state=active]:flex data-[state=active]:flex-col">
          <ConversationTab agentId={agentId} isConnected={isConnected} />
        </TabsContent>

        <TabsContent value="tools" className="flex-1 mt-0 overflow-hidden data-[state=active]:flex data-[state=active]:flex-col">
          <ToolCallsTab agentId={agentId} />
        </TabsContent>

        <TabsContent value="signals" className="flex-1 mt-0 overflow-hidden data-[state=active]:flex data-[state=active]:flex-col">
          <SignalsTab agentId={agentId} />
        </TabsContent>
      </Tabs>
    </Card>
  )
}
