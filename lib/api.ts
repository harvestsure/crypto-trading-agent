/**
 * API Service - REST API calls to Python backend
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

interface ApiResponse<T> {
  data?: T
  error?: string
}

async function fetchApi<T>(endpoint: string, options: RequestInit = {}): Promise<ApiResponse<T>> {
  try {
    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...options.headers,
      },
    })

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: "Request failed" }))
      return { error: error.detail || "Request failed" }
    }

    const data = await response.json()
    return { data }
  } catch (error) {
    return { error: error instanceof Error ? error.message : "Network error" }
  }
}

export { API_BASE_URL }

// Health check
export async function checkHealth() {
  return fetchApi<{
    status: string
    timestamp: string
    exchanges_connected: number
    models_registered: number
  }>("/health")
}

// ============== AI Models ==============

export async function getModels() {
  return fetchApi<{
    models: Array<{
      id: string
      name: string
      provider: string
      model: string
      base_url?: string
      status: string
      created_at: string
    }>
  }>("/api/models")
}

export async function getModel(modelId: string) {
  return fetchApi<{
    id: string
    name: string
    provider: string
    model: string
    base_url?: string
    status: string
    created_at: string
  }>(`/api/models/${modelId}`)
}

export async function createModel(model: {
  id: string
  name: string
  provider: string
  api_key: string
  base_url?: string
  model: string
}) {
  return fetchApi<{ status: string; model_id: string }>("/api/models", {
    method: "POST",
    body: JSON.stringify(model),
  })
}

export async function updateModel(modelId: string, data: { status?: string }) {
  return fetchApi<{ status: string }>(`/api/models/${modelId}`, {
    method: "PUT",
    body: JSON.stringify(data),
  })
}

export async function deleteModel(modelId: string) {
  return fetchApi<{ status: string }>(`/api/models/${modelId}`, {
    method: "DELETE",
  })
}

// ============== Exchanges ==============

export async function getExchanges() {
  return fetchApi<{
    exchanges: Array<{
      id: string
      name: string
      exchange: string
      testnet: boolean
      status: string
      created_at: string
    }>
  }>("/api/exchanges")
}

export async function getExchange(exchangeId: string) {
  return fetchApi<{
    id: string
    name: string
    exchange: string
    testnet: boolean
    status: string
    created_at: string
  }>(`/api/exchanges/${exchangeId}`)
}

export async function connectExchange(exchange: {
  id: string
  name: string
  exchange: string
  api_key: string
  secret_key: string
  passphrase?: string
  testnet: boolean
}) {
  return fetchApi<{ status: string; exchange_id: string }>("/api/exchanges", {
    method: "POST",
    body: JSON.stringify(exchange),
  })
}

// Backwards-compatible alias used by client store
export async function createExchange(exchange: {
  id: string
  name: string
  exchange: string
  api_key: string
  secret_key: string
  passphrase?: string
  testnet: boolean
}) {
  return connectExchange(exchange)
}

export async function updateExchange(exchangeId: string, data: { status?: string }) {
  return fetchApi<{ status: string }>(`/api/exchanges/${exchangeId}`, {
    method: "PUT",
    body: JSON.stringify(data),
  })
}

export async function disconnectExchange(exchangeId: string) {
  return fetchApi<{ status: string }>(`/api/exchanges/${exchangeId}`, {
    method: "DELETE",
  })
}

// Backwards-compatible alias used by client store
export async function deleteExchange(exchangeId: string) {
  return disconnectExchange(exchangeId)
}

// ============== Agents ==============

export async function getAgents() {
  return fetchApi<{
    agents: Array<{
      id: string
      name: string
      model_id: string
      exchange_id: string
      symbol: string
      timeframe: string
      indicators: string[]
      prompt: string
      status: string
      max_position_size?: number
      risk_per_trade?: number
      default_leverage?: number
      created_at: string
      performance?: {
        total_trades: number
        win_rate: number
        pnl: number
      }
    }>
  }>("/api/agents")
}

export async function getAgent(agentId: string) {
  return fetchApi<{
    id: string
    name: string
    model_id: string
    exchange_id: string
    symbol: string
    timeframe: string
    indicators: string[]
    prompt: string
    status: string
    max_position_size?: number
    risk_per_trade?: number
    default_leverage?: number
    created_at: string
    performance?: {
      total_trades: number
      win_rate: number
      pnl: number
    }
  }>(`/api/agents/${agentId}`)
}

export async function createAgent(agent: {
  id: string
  name: string
  model_id: string
  exchange_id: string
  symbol: string
  timeframe: string
  indicators: string[]
  prompt: string
  max_position_size?: number
  risk_per_trade?: number
  default_leverage?: number
}) {
  return fetchApi<{ status: string; agent_id: string }>("/api/agents", {
    method: "POST",
    body: JSON.stringify(agent),
  })
}

export async function updateAgent(agentId: string, data: { status?: string }) {
  return fetchApi<{ status: string }>(`/api/agents/${agentId}`, {
    method: "PUT",
    body: JSON.stringify(data),
  })
}

export async function deleteAgent(agentId: string) {
  return fetchApi<{ status: string }>(`/api/agents/${agentId}`, { method: "DELETE" })
}

export async function triggerAnalysis(agentId: string) {
  return fetchApi<{
    action: string
    reason: string
    indicators: Record<string, unknown>
  }>(`/api/agents/${agentId}/analyze`, { method: "POST" })
}

export async function getAgentPositions(agentId: string) {
  return fetchApi<{
    positions: Array<{
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
      timestamp: string
    }>
  }>(`/api/agents/${agentId}/positions`)
}

export async function getAgentBalance(agentId: string) {
  return fetchApi<{
    totalBalance: number
    availableBalance: number
    usedMargin: number
    unrealizedPnl: number
    realizedPnl: number
    todayPnl: number
    weekPnl: number
    monthPnl: number
  }>(`/api/agents/${agentId}/balance`)
}

export async function getAgentConversations(agentId: string, limit = 50) {
  return fetchApi<{
    conversations: Array<{
      id: string
      role: "system" | "user" | "assistant" | "tool"
      content: string
      timestamp: string
      toolCall?: {
        id: string
        name: string
        arguments: Record<string, unknown>
        result: string
        status: "success" | "error" | "pending"
      }
    }>
  }>(`/api/agents/${agentId}/conversations?limit=${limit}`)
}

export async function getAgentToolCalls(agentId: string, limit = 50) {
  return fetchApi<{
    toolCalls: Array<{
      id: string
      name: string
      arguments: Record<string, unknown>
      result: string
      status: "success" | "error" | "pending"
      timestamp: string
    }>
  }>(`/api/agents/${agentId}/tool-calls?limit=${limit}`)
}

export async function getAgentOrders(agentId: string, limit = 50) {
  return fetchApi<{
    orders: Array<{
      id: string
      symbol: string
      side: "buy" | "sell"
      type: "market" | "limit" | "stop"
      amount: number
      price: number | null
      filled: number
      status: string
      timestamp: number
    }>
  }>(`/api/agents/${agentId}/orders?limit=${limit}`)
}

export async function getAgentProfitHistory(agentId: string, days = 30) {
  return fetchApi<{
    profitHistory: Array<{
      timestamp: number
      balance: number
      pnl: number
      pnlPercent: number
    }>
  }>(`/api/agents/${agentId}/profit-history?days=${days}`)
}

export async function getAgentSignals(agentId: string, limit = 50) {
  return fetchApi<{
    signals: Array<{
      id: string
      action: "buy" | "sell" | "hold"
      reason: string
      price: number
      takeProfit?: number
      stopLoss?: number
      timestamp: string
    }>
  }>(`/api/agents/${agentId}/signals?limit=${limit}`)
}

export async function getAgentLogs(agentId: string, limit = 100) {
  return fetchApi<{
    logs: Array<{
      id: string
      level: "info" | "warning" | "error" | "success"
      message: string
      timestamp: string
    }>
  }>(`/api/agents/${agentId}/logs?limit=${limit}`)
}

export async function startAgent(agentId: string) {
  return fetchApi<{ status: string }>(`/api/agents/${agentId}/start`, { method: "POST" })
}

export async function stopAgent(agentId: string) {
  return fetchApi<{ status: string }>(`/api/agents/${agentId}/stop`, { method: "POST" })
}

// ============== Orders ==============

export async function placeOrder(order: {
  agent_id: string
  symbol: string
  side: "buy" | "sell"
  order_type: "market" | "limit"
  amount: number
  price?: number
}) {
  return fetchApi<{
    id: string
    status: string
    symbol: string
    side: string
    amount: number
    price?: number
  }>("/api/orders", {
    method: "POST",
    body: JSON.stringify(order),
  })
}

// ============== Market Data ==============

export async function getTicker(exchangeId: string, symbol: string) {
  return fetchApi<{
    ticker: {
      last: number
      bid: number
      ask: number
      volume: number
      change: number
    }
  }>(`/api/ticker/${exchangeId}/${encodeURIComponent(symbol)}`)
}

export async function getKlines(exchangeId: string, symbol: string, timeframe: string, limit = 100) {
  return fetchApi<{
    klines: Array<[number, number, number, number, number, number]>
  }>(`/api/klines/${exchangeId}/${encodeURIComponent(symbol)}/${timeframe}?limit=${limit}`)
}

export async function getIndicators(exchangeId: string, symbol: string, timeframe: string, indicators: string[]) {
  const query = new URLSearchParams({
    exchange_id: exchangeId,
    symbol,
    timeframe,
    indicators: indicators.join(","),
  })
  return fetchApi<{
    indicators: Record<string, number | Record<string, number>>
  }>(`/api/indicators?${query}`)
}

// ============== Market Analysis ==============

export async function analyzeMarket(params: {
  model_id: string
  symbol: string
  timeframe: string
  indicators: string[]
}) {
  const query = new URLSearchParams({
    model_id: params.model_id,
    symbol: params.symbol,
    timeframe: params.timeframe,
    indicators: params.indicators.join(","),
  })

  return fetchApi<{
    action: string
    reason: string
    indicators: string[]
  }>(`/api/analyze?${query}`)
}
