"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Bot, User, Wrench, AlertCircle, CheckCircle2, Loader2 } from "lucide-react"
import { cn } from "@/lib/utils"
import type { ConversationMessage } from "@/lib/types"

interface ConversationHistoryProps {
  messages: ConversationMessage[]
}

export function ConversationHistory({ messages }: ConversationHistoryProps) {
  const getIcon = (role: string) => {
    switch (role) {
      case "user":
      case "system":
        return <User className="h-4 w-4" />
      case "assistant":
        return <Bot className="h-4 w-4" />
      case "tool":
        return <Wrench className="h-4 w-4" />
      default:
        return <Bot className="h-4 w-4" />
    }
  }

  const getRoleStyle = (role: string) => {
    switch (role) {
      case "user":
        return "bg-primary/10 border-primary/20"
      case "assistant":
        return "bg-secondary border-border"
      case "system":
        return "bg-warning/10 border-warning/20"
      case "tool":
        return "bg-chart-3/10 border-chart-3/20"
      default:
        return "bg-secondary border-border"
    }
  }

  return (
    <Card className="h-full">
      <CardHeader className="pb-2">
        <CardTitle className="text-base flex items-center gap-2">
          <Bot className="h-4 w-4" />
          AI Conversation History
        </CardTitle>
      </CardHeader>
      <CardContent>
        <ScrollArea className="pr-4">
          <div className="space-y-3">
            {messages.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-8">No conversation history yet</p>
            ) : (
              messages.map((msg) => (
                <div key={msg.id} className={cn("rounded-lg border p-3 space-y-2", getRoleStyle(msg.role))}>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      {getIcon(msg.role)}
                      <span className="text-xs font-medium text-foreground capitalize">{msg.role}</span>
                    </div>
                    <span className="text-xs text-muted-foreground">
                      {new Date(msg.timestamp).toLocaleTimeString()}
                    </span>
                  </div>

                  <p className="text-sm text-foreground whitespace-pre-wrap">{msg.content}</p>

                  {msg.toolCall && (
                    <div className="mt-2 rounded bg-background/50 p-2 space-y-1">
                      <div className="flex items-center gap-2">
                        <Wrench className="h-3 w-3 text-chart-3" />
                        <span className="text-xs font-mono text-chart-3">{msg.toolCall.name}</span>
                        {msg.toolCall.status === "pending" && (
                          <Loader2 className="h-3 w-3 animate-spin text-muted-foreground" />
                        )}
                        {msg.toolCall.status === "success" && <CheckCircle2 className="h-3 w-3 text-success" />}
                        {msg.toolCall.status === "error" && <AlertCircle className="h-3 w-3 text-destructive" />}
                      </div>
                      <pre className="text-xs text-muted-foreground overflow-x-auto">
                        {JSON.stringify(msg.toolCall.arguments, null, 2)}
                      </pre>
                      {msg.toolCall.result && (
                        <div className="text-xs text-foreground mt-1 pt-1 border-t border-border">
                          Result: {msg.toolCall.result}
                        </div>
                      )}
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
