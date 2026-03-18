"use client"

import { useState, useEffect, useRef } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
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
  ChevronDown,
  ChevronUp,
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

// ---- Helpers ----
const ACTION_CONFIG: Record<string, { label: string; className: string; icon: React.ReactNode }> = {
  LONG: { label: "LONG", className: "bg-success/15 text-success border-success/30", icon: <TrendingUp className="h-3 w-3" /> },
  SHORT: { label: "SHORT", className: "bg-destructive/15 text-destructive border-destructive/30", icon: <TrendingDown className="h-3 w-3" /> },
  CLOSE: { label: "CLOSE", className: "bg-warning/15 text-warning border-warning/30", icon: <Minus className="h-3 w-3" /> },
  HOLD: { label: "HOLD", className: "bg-muted text-muted-foreground border-border", icon: <Minus className="h-3 w-3" /> },
  BUY: { label: "BUY", className: "bg-success/15 text-success border-success/30", icon: <TrendingUp className="h-3 w-3" /> },
  SELL: { label: "SELL", className: "bg-destructive/15 text-destructive border-destructive/30", icon: <TrendingDown className="h-3 w-3" /> },
}

function ActionBadge({ action }: { action: string }) {
  const cfg = ACTION_CONFIG[action?.toUpperCase()] ?? ACTION_CONFIG["HOLD"]
  return (
    <Badge variant="outline" className={cn("flex items-center gap-1 text-xs font-semibold px-1.5 py-0", cfg.className)}>
      {cfg.icon}
      {cfg.label}
    </Badge>
  )
}

const ROLE_META: Record<string, { icon: React.ReactNode; label: string; bubble: string }> = {
  user:      { icon: <User className="h-3 w-3" />,    label: "User",      bubble: "bg-primary/8 border-primary/20" },
  assistant: { icon: <Bot className="h-3 w-3" />,     label: "Agent",     bubble: "bg-secondary border-border" },
  system:    { icon: <Zap className="h-3 w-3" />,     label: "System",    bubble: "bg-warning/8 border-warning/20" },
  tool:      { icon: <Wrench className="h-3 w-3" />,  label: "Tool",      bubble: "bg-chart-3/8 border-chart-3/20" },
}

function formatTime(ts: Date | string | undefined) {
  if (!ts) return ""
  const d = ts instanceof Date ? ts : new Date(ts)
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
}

// ---- Message bubble with expand/collapse ----
function MessageBubble({ msg }: { msg: ConversationMessage }) {
  const [expanded, setExpanded] = useState(false)
  const meta = ROLE_META[msg.role] ?? ROLE_META["assistant"]
  const isLong = (msg.content?.length ?? 0) > 200

  return (
    <div className={cn("rounded-lg border p-2.5 space-y-1.5 transition-colors", meta.bubble)}>
      {/* Header */}
      <div className="flex items-center justify-between gap-1">
        <div className="flex items-center gap-1.5 text-muted-foreground">
          {meta.icon}
          <span className="text-xs font-medium">{meta.label}</span>
        </div>
        <span className="text-xs text-muted-foreground shrink-0">{formatTime(msg.timestamp)}</span>
      </div>

      {/* Content — collapsed to 3 lines by default */}
      <p className={cn(
        "text-xs text-foreground leading-relaxed break-words",
        !expanded && isLong && "line-clamp-3",
      )}>
        {msg.content}
      </p>

      {/* Expand toggle */}
      {isLong && (
        <button
          onClick={() => setExpanded((v) => !v)}
          className="flex items-center gap-0.5 text-xs text-primary hover:underline"
        >
          {expanded ? <><ChevronUp className="h-3 w-3" /> Show less</> : <><ChevronDown className="h-3 w-3" /> Show more</>}
        </button>
      )}

      {/* Inline tool call */}
      {msg.toolCall && (
        <div className="rounded bg-background/60 border border-border p-2 space-y-1 mt-1">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-1.5">
              <Wrench className="h-3 w-3 text-chart-3" />
              <span className="text-xs font-mono text-chart-3 font-semibold">{msg.toolCall.name}</span>
            </div>
            {msg.toolCall.status === "pending" && <Clock className="h-3 w-3 text-muted-foreground" />}
            {msg.toolCall.status === "success" && <CheckCircle2 className="h-3 w-3 text-success" />}
            {msg.toolCall.status === "error" && <XCircle className="h-3 w-3 text-destructive" />}
          </div>
          <pre className="text-xs text-muted-foreground overflow-x-auto whitespace-pre-wrap break-all">
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
  )
}

// ---- Tab: Conversation ----
function ConversationTab({ agentId, isConnected }: { agentId: string; isConnected: boolean }) {
  const { conversations, isLoading, refresh } = useAgentConversations(agentId, true)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [conversations.length])

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-3 py-2 border-b shrink-0">
        <div className="flex items-center gap-1.5">
          <div className={cn("h-1.5 w-1.5 rounded-full", isConnected ? "bg-success" : "bg-muted-foreground")} />
          <span className="text-xs text-muted-foreground">{isConnected ? "Live" : "Offline"}</span>
        </div>
        <Button variant="ghost" size="sm" onClick={() => refresh()} disabled={isLoading} className="h-6 w-6 p-0">
          <RefreshCw className={cn("h-3 w-3", isLoading && "animate-spin")} />
        </Button>
      </div>
      <ScrollArea className="flex-1">
        <div className="flex flex-col gap-2 p-3">
          {conversations.length === 0 && !isLoading && (
            <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
              <Bot className="h-8 w-8 mb-2 opacity-30" />
              <p className="text-xs">No conversation yet</p>
            </div>
          )}
          {conversations.map((msg: ConversationMessage) => (
            <MessageBubble key={msg.id} msg={msg} />
          ))}
          <div ref={bottomRef} />
        </div>
      </ScrollArea>
    </div>
  )
}

// ---- Tab: Tool Calls ----
function ToolCallsTab({ agentId }: { agentId: string }) {
  const { toolCalls, isLoading, refresh } = useAgentToolCalls(agentId, true)

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-end px-3 py-2 border-b shrink-0">
        <Button variant="ghost" size="sm" onClick={() => refresh()} disabled={isLoading} className="h-6 w-6 p-0">
          <RefreshCw className={cn("h-3 w-3", isLoading && "animate-spin")} />
        </Button>
      </div>
      <ScrollArea className="flex-1">
        <div className="flex flex-col gap-2 p-3">
          {toolCalls.length === 0 && !isLoading && (
            <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
              <Wrench className="h-8 w-8 mb-2 opacity-30" />
              <p className="text-xs">No tool calls yet</p>
            </div>
          )}
          {toolCalls.map((tc: ToolCall) => (
            <div key={tc.id} className="rounded-lg border border-chart-3/20 bg-chart-3/5 p-2.5 space-y-2">
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-1.5">
                  <Wrench className="h-3 w-3 text-chart-3" />
                  <span className="text-xs font-semibold font-mono">{tc.name}</span>
                </div>
                <span className="shrink-0">
                  {tc.status === "success" && <CheckCircle2 className="h-3.5 w-3.5 text-success" />}
                  {tc.status === "error"   && <XCircle className="h-3.5 w-3.5 text-destructive" />}
                  {tc.status === "pending" && <Clock className="h-3.5 w-3.5 text-muted-foreground" />}
                </span>
              </div>
              <pre className="text-xs text-muted-foreground bg-background/60 rounded p-1.5 overflow-x-auto border border-border whitespace-pre-wrap break-all">
                {JSON.stringify(tc.arguments, null, 2)}
              </pre>
              {tc.result && (
                <p className="text-xs bg-success/10 rounded p-1.5 border border-success/20 text-foreground break-words">
                  {tc.result}
                </p>
              )}
              <p className="text-xs text-muted-foreground text-right">{formatTime(tc.timestamp)}</p>
            </div>
          ))}
        </div>
      </ScrollArea>
    </div>
  )
}

// ---- Tab: Signals ----
function SignalsTab({ agentId }: { agentId: string }) {
  const { signals, isLoading, refresh } = useAgentSignals(agentId, true)

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-end px-3 py-2 border-b shrink-0">
        <Button variant="ghost" size="sm" onClick={() => refresh()} disabled={isLoading} className="h-6 w-6 p-0">
          <RefreshCw className={cn("h-3 w-3", isLoading && "animate-spin")} />
        </Button>
      </div>
      <ScrollArea className="flex-1">
        <div className="flex flex-col gap-2 p-3">
          {signals.length === 0 && !isLoading && (
            <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
              <Signal className="h-8 w-8 mb-2 opacity-30" />
              <p className="text-xs">No signals yet</p>
            </div>
          )}
          {signals.map((signal: any) => {
            const snapshot = signal.indicators_snapshot ?? {}
            const action = (signal.action ?? "HOLD").toUpperCase()
            return (
              <div
                key={signal.id}
                className={cn(
                  "rounded-lg border p-2.5 space-y-2",
                  action === "LONG"  ? "bg-success/8 border-success/20" :
                  action === "SHORT" ? "bg-destructive/8 border-destructive/20" :
                  "bg-muted/40 border-border",
                )}
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-1.5">
                    <ActionBadge action={action} />
                    {snapshot.symbol && (
                      <span className="text-xs font-mono text-muted-foreground">{snapshot.symbol}</span>
                    )}
                  </div>
                  <span className="text-xs text-muted-foreground shrink-0">{formatTime(signal.timestamp)}</span>
                </div>

                {signal.reason && (
                  <p className="text-xs text-foreground leading-relaxed line-clamp-3">{signal.reason}</p>
                )}

                {(snapshot.price || signal.take_profit || signal.stop_loss || snapshot.amount) && (
                  <div className="grid grid-cols-2 gap-x-3 gap-y-0.5 text-xs">
                    {snapshot.price && (
                      <span className="text-muted-foreground">
                        Price: <span className="font-mono text-foreground">${Number(snapshot.price).toLocaleString()}</span>
                      </span>
                    )}
                    {snapshot.amount && (
                      <span className="text-muted-foreground">
                        Size: <span className="font-mono text-foreground">{snapshot.amount}</span>
                      </span>
                    )}
                    {signal.take_profit && (
                      <span>
                        TP: <span className="font-mono text-success">${Number(signal.take_profit).toLocaleString()}</span>
                      </span>
                    )}
                    {signal.stop_loss && (
                      <span>
                        SL: <span className="font-mono text-destructive">${Number(signal.stop_loss).toLocaleString()}</span>
                      </span>
                    )}
                  </div>
                )}

                {signal.confidence != null && (
                  <div className="flex items-center gap-2">
                    <div className="flex-1 h-1 bg-border rounded-full overflow-hidden">
                      <div
                        className={cn("h-full rounded-full", action === "LONG" ? "bg-success" : action === "SHORT" ? "bg-destructive" : "bg-muted-foreground")}
                        style={{ width: `${Math.min(100, signal.confidence * 100)}%` }}
                      />
                    </div>
                    <span className="text-xs text-muted-foreground shrink-0">{(signal.confidence * 100).toFixed(0)}%</span>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </ScrollArea>
    </div>
  )
}

// ---- Main Component ----
type TabId = "conversations" | "tools" | "signals"

export function AgentConversationViewer({ agentId }: AgentConversationViewerProps) {
  const { isConnected } = useBackendStatus()
  const [activeTab, setActiveTab] = useState<TabId>("conversations")

  const { conversations } = useAgentConversations(agentId, true)
  const { toolCalls } = useAgentToolCalls(agentId, true)
  const { signals } = useAgentSignals(agentId, true)

  const tabs: { id: TabId; label: string; icon: React.ReactNode; count: number }[] = [
    { id: "conversations", label: "Chat",    icon: <MessageSquare className="h-3.5 w-3.5" />, count: conversations.length },
    { id: "tools",         label: "Tools",   icon: <Wrench className="h-3.5 w-3.5" />,        count: toolCalls.length },
    { id: "signals",       label: "Signals", icon: <Signal className="h-3.5 w-3.5" />,        count: signals.length },
  ]

  return (
    <Card className="flex flex-col h-full overflow-hidden">
      {/* Panel header */}
      <CardHeader className="pb-0 pt-3 px-4 shrink-0 border-b">
        <div className="flex items-center gap-2 mb-2">
          <Bot className="h-4 w-4 text-primary" />
          <CardTitle className="text-sm font-semibold">AI Activity</CardTitle>
        </div>
        {/* Custom tab bar */}
        <div className="flex gap-1 -mb-px">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={cn(
                "flex items-center gap-1.5 px-3 py-2 text-xs font-medium border-b-2 transition-colors",
                activeTab === tab.id
                  ? "border-primary text-primary"
                  : "border-transparent text-muted-foreground hover:text-foreground",
              )}
            >
              {tab.icon}
              {tab.label}
              {tab.count > 0 && (
                <span className={cn(
                  "rounded-full px-1.5 py-0 text-xs font-mono leading-4 min-w-[18px] text-center",
                  activeTab === tab.id ? "bg-primary/15 text-primary" : "bg-muted text-muted-foreground",
                )}>
                  {tab.count}
                </span>
              )}
            </button>
          ))}
        </div>
      </CardHeader>

      {/* Tab content */}
      <CardContent className="flex-1 min-h-0 p-0">
        <div className="h-full">
          {activeTab === "conversations" && <ConversationTab agentId={agentId} isConnected={isConnected} />}
          {activeTab === "tools"         && <ToolCallsTab agentId={agentId} />}
          {activeTab === "signals"       && <SignalsTab agentId={agentId} />}
        </div>
      </CardContent>
    </Card>
  )
}
