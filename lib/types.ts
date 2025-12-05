export interface AIModel {
  id: string
  name: string
  provider: "openai" | "anthropic" | "deepseek" | "custom"
  apiKey: string
  baseUrl?: string
  model: string
  createdAt: Date
  status: "active" | "inactive"
}

export interface Exchange {
  id: string
  name: string
  exchange: "binance" | "okx" | "bybit" | "bitget" | "gate"
  apiKey: string
  secretKey: string
  passphrase?: string
  testnet: boolean
  createdAt: Date
  status: "connected" | "disconnected" | "error"
}

export interface TradingAgent {
  id: string
  name: string
  modelId: string
  exchangeId: string
  symbol: string
  timeframe: "1m" | "5m" | "15m" | "30m" | "1h" | "4h" | "1d"
  indicators: string[]
  prompt: string
  status: "running" | "paused" | "stopped"
  createdAt: Date
  lastSignal?: {
    action: "buy" | "sell" | "hold"
    timestamp: Date
    reason: string
  }
  performance?: {
    totalTrades: number
    winRate: number
    pnl: number
  }
}

export interface Order {
  id: string
  agentId: string
  symbol: string
  side: "buy" | "sell"
  type: "market" | "limit" | "stop_loss" | "take_profit"
  amount: number
  price?: number
  status: "pending" | "filled" | "canceled"
  createdAt: Date
}

export interface Position {
  symbol: string
  side: "long" | "short"
  size: number
  entryPrice: number
  currentPrice: number
  leverage: number
  unrealizedPnl: number
  unrealizedPnlPercent: number
  liquidationPrice: number
  margin: number
  timestamp: Date
}

export interface AccountBalance {
  totalBalance: number
  availableBalance: number
  usedMargin: number
  unrealizedPnl: number
  realizedPnl: number
  todayPnl: number
  weekPnl: number
  monthPnl: number
}

export interface ConversationMessage {
  id: string
  role: "user" | "assistant" | "system" | "tool"
  content: string
  timestamp: Date
  toolCall?: ToolCall
}

export interface ToolCall {
  id: string
  name: string
  arguments: Record<string, unknown>
  result?: string
  status: "pending" | "success" | "error"
  timestamp: Date
}

export interface ProfitDataPoint {
  timestamp: number
  balance: number
  pnl: number
  pnlPercent: number
}

export interface KlineData {
  timestamp: number
  open: number
  high: number
  low: number
  close: number
  volume: number
}
