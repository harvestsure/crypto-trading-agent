/**
 * WebSocket Service - Real-time communication with Python backend
 * Designed to work gracefully when backend is not available (demo mode)
 */

type MessageHandler = (message: WebSocketMessage) => void
type StatusHandler = (status: "connected" | "disconnected" | "error") => void

export interface WebSocketMessage {
  type: string
  [key: string]: unknown
}

export interface KlineMessage extends WebSocketMessage {
  type: "kline"
  exchange_id: string
  symbol: string
  timeframe: string
  data: Array<{
    timestamp: number
    open: number
    high: number
    low: number
    close: number
    volume: number
  }>
}

export interface SignalMessage extends WebSocketMessage {
  type: "signal"
  agent_id: string
  signal: {
    action: "buy" | "sell" | "hold"
    reason: string
    take_profit?: number
    stop_loss?: number
  }
  indicators: Record<string, number>
}

class WebSocketService {
  private ws: WebSocket | null = null
  private reconnectAttempts = 0
  private maxReconnectAttempts = 3 // Reduced max attempts
  private reconnectDelay = 2000
  private clientId: string
  private messageHandlers: Set<MessageHandler> = new Set()
  private statusHandlers: Set<StatusHandler> = new Set()
  private pingInterval: NodeJS.Timeout | null = null
  private isManuallyConnecting = false // Track manual connection

  constructor() {
    this.clientId = `client_${Date.now()}_${Math.random().toString(36).slice(2)}`
  }

  private shouldConnect(): boolean {
    // Only connect if explicitly requested and we have a valid URL
    const wsUrl = process.env.NEXT_PUBLIC_WS_URL
    return !!wsUrl && this.isManuallyConnecting
  }

  connect(url?: string) {
    const wsUrl = url || process.env.NEXT_PUBLIC_WS_URL

    if (!wsUrl) {
      console.log("[WebSocket] No backend URL configured - running in demo mode")
      this.notifyStatus("disconnected")
      return
    }

    if (typeof window === "undefined") {
      return
    }

    this.isManuallyConnecting = true

    try {
      this.ws = new WebSocket(`${wsUrl}/ws/${this.clientId}`)

      this.ws.onopen = () => {
        console.log("[WebSocket] Connected")
        this.reconnectAttempts = 0
        this.notifyStatus("connected")
        this.startPing()
      }

      this.ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data) as WebSocketMessage
          this.notifyMessage(message)
        } catch (error) {
          console.error("[WebSocket] Failed to parse message:", error)
        }
      }

      this.ws.onclose = () => {
        console.log("[WebSocket] Disconnected")
        this.notifyStatus("disconnected")
        this.stopPing()
        this.attemptReconnect()
      }

      this.ws.onerror = () => {
        this.notifyStatus("disconnected")
        this.ws?.close()
      }
    } catch {
      console.log("[WebSocket] Backend not available - running in demo mode")
      this.notifyStatus("disconnected")
    }
  }

  private attemptReconnect() {
    if (this.isManuallyConnecting && this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++
      const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1)
      console.log(`[WebSocket] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`)
      setTimeout(() => this.connect(), delay)
    } else if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.log("[WebSocket] Max reconnection attempts reached - running in demo mode")
      this.isManuallyConnecting = false
    }
  }

  private startPing() {
    this.pingInterval = setInterval(() => {
      this.send({ type: "ping" })
    }, 30000)
  }

  private stopPing() {
    if (this.pingInterval) {
      clearInterval(this.pingInterval)
      this.pingInterval = null
    }
  }

  disconnect() {
    this.isManuallyConnecting = false
    this.stopPing()
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
  }

  send(message: WebSocketMessage) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message))
    }
  }

  subscribeKline(exchangeId: string, symbol: string, timeframe: string) {
    this.send({
      type: "subscribe_kline",
      exchange_id: exchangeId,
      symbol,
      timeframe,
    })
  }

  requestAnalysis(params: {
    agentId: string
    modelId: string
    klineData: Array<{
      timestamp: number
      open: number
      high: number
      low: number
      close: number
      volume: number
    }>
    indicators: string[]
    prompt: string
  }) {
    this.send({
      type: "analyze",
      agent_id: params.agentId,
      model_id: params.modelId,
      kline_data: params.klineData,
      indicators: params.indicators,
      prompt: params.prompt,
    })
  }

  onMessage(handler: MessageHandler) {
    this.messageHandlers.add(handler)
    return () => this.messageHandlers.delete(handler)
  }

  private notifyMessage(message: WebSocketMessage) {
    this.messageHandlers.forEach((handler) => handler(message))
  }

  onStatusChange(handler: StatusHandler) {
    this.statusHandlers.add(handler)
    return () => this.statusHandlers.delete(handler)
  }

  private notifyStatus(status: "connected" | "disconnected" | "error") {
    this.statusHandlers.forEach((handler) => handler(status))
  }

  get isConnected() {
    return this.ws?.readyState === WebSocket.OPEN
  }
}

export const wsService = new WebSocketService()
