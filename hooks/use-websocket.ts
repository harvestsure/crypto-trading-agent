"use client"

import { useEffect, useState, useCallback } from "react"
import { wsService, type WebSocketMessage } from "@/lib/websocket"

export function useWebSocket(autoConnect = false) {
  const [status, setStatus] = useState<"connected" | "disconnected" | "error">("disconnected")
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null)

  useEffect(() => {
    const unsubStatus = wsService.onStatusChange(setStatus)
    const unsubMessage = wsService.onMessage(setLastMessage)

    if (autoConnect && process.env.NEXT_PUBLIC_WS_URL && !wsService.isConnected) {
      wsService.connect()
    }

    return () => {
      unsubStatus()
      unsubMessage()
    }
  }, [autoConnect])

  const connect = useCallback(() => {
    wsService.connect()
  }, [])

  const disconnect = useCallback(() => {
    wsService.disconnect()
  }, [])

  const send = useCallback((message: WebSocketMessage) => {
    wsService.send(message)
  }, [])

  const subscribeKline = useCallback((exchangeId: string, symbol: string, timeframe: string) => {
    wsService.subscribeKline(exchangeId, symbol, timeframe)
  }, [])

  const requestAnalysis = useCallback((params: Parameters<typeof wsService.requestAnalysis>[0]) => {
    wsService.requestAnalysis(params)
  }, [])

  return {
    status,
    isConnected: status === "connected",
    lastMessage,
    connect,
    disconnect,
    send,
    subscribeKline,
    requestAnalysis,
  }
}
