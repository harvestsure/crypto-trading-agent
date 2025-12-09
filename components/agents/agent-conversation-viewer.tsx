"use client"

import { useEffect, useState, useRef } from "react"
import useSWR from "swr"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Button } from "@/components/ui/button"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Bot, User, Wrench, RefreshCw, Zap, CheckCircle2, XCircle, Clock, MessageSquare } from "lucide-react"
import { cn } from "@/lib/utils"
import { API_BASE_URL } from "@/lib/api"
import type { ConversationMessage, ToolCall } from "@/lib/types"

interface AgentConversationProps {
  agentId: string
}

interface ConversationResponse {
  agent_id: string
  conversations: ConversationMessage[]
  count: number
}

interface ToolCallsResponse {
  agent_id: string
  tool_calls: ToolCall[]
  count: number
}

interface SignalsResponse {
  agent_id: string
  signals: any[]
  count: number
}

const apiUrl = (path: string) => `${API_BASE_URL}${path}`

export function AgentConversationViewer({ agentId }: AgentConversationProps) {
  const [ws, setWs] = useState<WebSocket | null>(null)
  const [isConnected, setIsConnected] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)

  const { data: conversationData, mutate: mutateConversation, isLoading: conversationLoading } = useSWR<ConversationResponse>(
    `/api/agents/${agentId}/conversations?limit=100`,
    async (url) => {
      const res = await fetch(apiUrl(url))
      if (!res.ok) throw new Error("Failed to fetch")
      return res.json()
    },
    { refreshInterval: 5000 }
  )

  const { data: toolCallsData, mutate: mutateToolCalls, isLoading: toolCallsLoading } = useSWR<ToolCallsResponse>(
    `/api/agents/${agentId}/tool-calls?limit=50`,
    async (url) => {
      const res = await fetch(apiUrl(url))
      if (!res.ok) throw new Error("Failed to fetch")
      return res.json()
    },
    { refreshInterval: 5000 }
  )

  const { data: signalsData, mutate: mutateSignals, isLoading: signalsLoading } = useSWR<SignalsResponse>(
    `/api/agents/${agentId}/signals?limit=50`,
    async (url) => {
      const res = await fetch(apiUrl(url))
      if (!res.ok) throw new Error("Failed to fetch")
      return res.json()
    },
    { refreshInterval: 5000 }
  )

  // WebSocket 实时连接
  useEffect(() => {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:"
    const backendHost = new URL(API_BASE_URL).host
    const wsUrl = `${protocol}//${backendHost}/api/agents/ws/${agentId}/stream`

    const websocket = new WebSocket(wsUrl)

    websocket.onopen = () => {
      setIsConnected(true)
      console.log("WebSocket connected")
      // 发送心跳
      websocket.send(JSON.stringify({ type: "ping" }))
    }

    websocket.onmessage = (event) => {
      const message = JSON.parse(event.data)
      console.log("WebSocket message:", message)

      // 根据消息类型更新数据
      if (message.type === "conversation" || message.type === "pong") {
        mutateConversation()
      } else if (message.type === "signal") {
        mutateSignals()
      } else if (message.type === "tool") {
        mutateToolCalls()
      }
    }

    websocket.onerror = (error) => {
      console.error("WebSocket error:", error)
      setIsConnected(false)
    }

    websocket.onclose = () => {
      setIsConnected(false)
      console.log("WebSocket disconnected")
    }

    setWs(websocket)

    return () => {
      if (websocket.readyState === WebSocket.OPEN) {
        websocket.close()
      }
    }
  }, [agentId, mutateConversation, mutateSignals, mutateToolCalls])

  // 自动滚动到底部
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [conversationData])

  const getMessageIcon = (role: string) => {
    switch (role) {
      case "user":
        return <User className="h-4 w-4 text-blue-500" />
      case "assistant":
        return <Bot className="h-4 w-4 text-green-500" />
      case "system":
        return <Zap className="h-4 w-4 text-yellow-500" />
      case "tool":
        return <Wrench className="h-4 w-4 text-purple-500" />
      default:
        return <MessageSquare className="h-4 w-4" />
    }
  }

  const getMessageColor = (role: string) => {
    switch (role) {
      case "user":
        return "bg-blue-50 border-blue-200"
      case "assistant":
        return "bg-green-50 border-green-200"
      case "system":
        return "bg-yellow-50 border-yellow-200"
      case "tool":
        return "bg-purple-50 border-purple-200"
      default:
        return "bg-gray-50 border-gray-200"
    }
  }

  const getToolStatus = (tool: any) => {
    if (tool.status === "success") {
      return (
        <div className="flex items-center gap-1 text-green-600">
          <CheckCircle2 className="h-4 w-4" />
          <span className="text-xs">Success</span>
        </div>
      )
    } else if (tool.status === "failed") {
      return (
        <div className="flex items-center gap-1 text-red-600">
          <XCircle className="h-4 w-4" />
          <span className="text-xs">Failed</span>
        </div>
      )
    }
    return null
  }

  return (
    <div className="space-y-4">
      <Tabs defaultValue="conversations" className="w-full">
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="conversations">
            对话 ({conversationData?.count || 0})
          </TabsTrigger>
          <TabsTrigger value="tools">
            工具调用 ({toolCallsData?.count || 0})
          </TabsTrigger>
          <TabsTrigger value="signals">
            交易信号 ({signalsData?.count || 0})
          </TabsTrigger>
        </TabsList>

        {/* 对话标签页 */}
        <TabsContent value="conversations">
          <Card className="h-full min-h-[600px]">
            <CardHeader className="pb-2 flex flex-row items-center justify-between">
              <CardTitle className="text-base flex items-center gap-2">
                <MessageSquare className="h-4 w-4" />
                AI Conversation History
              </CardTitle>
              <div className="flex items-center gap-2">
                <div
                  className={cn(
                    "h-2 w-2 rounded-full",
                    isConnected ? "bg-green-500" : "bg-red-500"
                  )}
                />
                <span className="text-xs text-gray-500">
                  {isConnected ? "Connected" : "Disconnected"}
                </span>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => mutateConversation()}
                  disabled={conversationLoading}
                >
                  <RefreshCw className={cn("h-4 w-4", conversationLoading && "animate-spin")} />
                </Button>
              </div>
            </CardHeader>

            <CardContent>
              <ScrollArea ref={scrollRef} className="h-[500px] w-full pr-4">
                <div className="space-y-3">
                  {conversationData?.conversations && conversationData.conversations.length > 0 ? (
                    conversationData.conversations.map((msg, idx) => (
                      <div key={idx} className={cn("rounded-lg border p-3", getMessageColor(msg.role))}>
                        <div className="flex items-start gap-2">
                          {getMessageIcon(msg.role)}
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center justify-between gap-2 mb-1">
                              <span className="text-xs font-semibold capitalize text-gray-700">
                                {msg.role}
                              </span>
                              <span className="text-xs text-gray-500">
                                {msg.timestamp ? new Date(msg.timestamp).toLocaleTimeString() : ""}
                              </span>
                            </div>
                            <p className="text-sm text-gray-700 break-word">
                              {msg.content}
                            </p>
                            {msg.toolCall && (
                              <div className="mt-2 text-xs bg-white/50 rounded p-2">
                                <span className="font-mono text-purple-700">
                                  {msg.toolCall.name}
                                </span>
                              </div>
                            )}
                          </div>
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className="flex items-center justify-center h-full text-gray-500">
                      No conversations yet
                    </div>
                  )}
                </div>
              </ScrollArea>
            </CardContent>
          </Card>
        </TabsContent>

        {/* 工具调用标签页 */}
        <TabsContent value="tools">
          <Card className="h-full min-h-[600px]">
            <CardHeader className="pb-2 flex flex-row items-center justify-between">
              <CardTitle className="text-base flex items-center gap-2">
                <Wrench className="h-4 w-4" />
                Tool Calls
              </CardTitle>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => mutateToolCalls()}
                disabled={toolCallsLoading}
              >
                <RefreshCw className={cn("h-4 w-4", toolCallsLoading && "animate-spin")} />
              </Button>
            </CardHeader>

            <CardContent>
              <ScrollArea className="h-[500px] w-full pr-4">
                <div className="space-y-3">
                  {toolCallsData?.tool_calls && toolCallsData.tool_calls.length > 0 ? (
                    toolCallsData.tool_calls.map((tool, idx) => (
                      <div key={idx} className="rounded-lg border border-purple-200 bg-purple-50 p-3">
                        <div className="flex items-start justify-between gap-2 mb-2">
                          <div className="flex items-center gap-2 flex-1">
                            <Wrench className="h-4 w-4 text-purple-500" />
                            <span className="font-semibold text-sm text-gray-700">
                              {tool.name}
                            </span>
                          </div>
                          {getToolStatus(tool)}
                        </div>

                        {tool.arguments && (
                          <div className="text-xs bg-white/50 rounded p-2 mb-2">
                            <p className="text-gray-600 font-mono">
                              {JSON.stringify(tool.arguments, null, 2)}
                            </p>
                          </div>
                        )}

                        {tool.result && (
                          <div className="text-xs bg-green-100 rounded p-2 mb-1">
                            <p className="text-gray-700">{tool.result}</p>
                          </div>
                        )}

                        <div className="flex items-center justify-between text-xs text-gray-500 mt-2">
                          <span>{(tool.timestamp ? new Date(tool.timestamp).getTime() : 0).toFixed(0)}ms</span>
                          <span>{tool.timestamp ? new Date(tool.timestamp).toLocaleTimeString() : ""}</span>
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className="flex items-center justify-center h-full text-gray-500">
                      No tool calls yet
                    </div>
                  )}
                </div>
              </ScrollArea>
            </CardContent>
          </Card>
        </TabsContent>

        {/* 交易信号标签页 */}
        <TabsContent value="signals">
          <Card className="h-full min-h-[600px]">
            <CardHeader className="pb-2 flex flex-row items-center justify-between">
              <CardTitle className="text-base flex items-center gap-2">
                <Zap className="h-4 w-4" />
                Trading Signals
              </CardTitle>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => mutateSignals()}
                disabled={signalsLoading}
              >
                <RefreshCw className={cn("h-4 w-4", signalsLoading && "animate-spin")} />
              </Button>
            </CardHeader>

            <CardContent>
              <ScrollArea className="h-[500px] w-full pr-4">
                <div className="space-y-3">
                  {signalsData?.signals && signalsData.signals.length > 0 ? (
                    signalsData.signals.map((signal, idx) => (
                      <div
                        key={idx}
                        className={cn(
                          "rounded-lg border p-3",
                          signal.action === "LONG"
                            ? "bg-green-50 border-green-200"
                            : signal.action === "SHORT"
                            ? "bg-red-50 border-red-200"
                            : "bg-yellow-50 border-yellow-200"
                        )}
                      >
                        <div className="flex items-start justify-between gap-2 mb-2">
                          <div className="flex items-center gap-2">
                            <Zap
                              className={cn(
                                "h-4 w-4",
                                signal.action === "LONG"
                                  ? "text-green-500"
                                  : signal.action === "SHORT"
                                  ? "text-red-500"
                                  : "text-yellow-500"
                              )}
                            />
                            <span className="font-semibold text-sm text-gray-700">
                              {signal.action} {signal.symbol}
                            </span>
                          </div>
                          <div className="flex items-center gap-2">
                            <span
                              className={cn(
                                "text-xs px-2 py-1 rounded",
                                signal.risk_level === "high"
                                  ? "bg-red-100 text-red-700"
                                  : signal.risk_level === "medium"
                                  ? "bg-yellow-100 text-yellow-700"
                                  : "bg-green-100 text-green-700"
                              )}
                            >
                              {signal.risk_level} risk
                            </span>
                            {signal.confidence && (
                              <span className="text-xs bg-white/50 rounded px-2 py-1">
                                {(signal.confidence * 100).toFixed(0)}% confident
                              </span>
                            )}
                          </div>
                        </div>

                        {signal.reason && (
                          <p className="text-sm text-gray-700 mb-2">{signal.reason}</p>
                        )}

                        <div className="text-xs text-gray-600 space-y-1">
                          {signal.recommended_entry && (
                            <div>Entry: {signal.recommended_entry}</div>
                          )}
                          {signal.recommended_exit && (
                            <div>Exit: {signal.recommended_exit}</div>
                          )}
                        </div>

                        <div className="text-xs text-gray-500 mt-2">
                          {signal.timestamp ? new Date(signal.timestamp).toLocaleString() : ""}
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className="flex items-center justify-center h-full text-gray-500">
                      No signals generated yet
                    </div>
                  )}
                </div>
              </ScrollArea>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
