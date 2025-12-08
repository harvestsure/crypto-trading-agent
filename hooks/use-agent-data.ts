"use client"

import useSWR from "swr"
import {
  getAgent,
  getAgentPositions,
  getAgentBalance,
  getAgentConversations,
  getAgentToolCalls,
  getAgentOrders,
  getAgentProfitHistory,
  getAgentSignals,
  getAgentLogs,
  getTicker,
  getIndicators,
  API_BASE_URL,
} from "@/lib/api"
import type { Position, AccountBalance, ConversationMessage, ToolCall, ProfitDataPoint } from "@/lib/types"

// Generic fetcher for SWR
const fetcher = async <T,>(key: string, apiFn: () => Promise<{ data?: T; error?: string }>): Promise<T | null> => {
  const result = await apiFn()
  if (result.error) {
    console.warn(`[v0] API Error for ${key}:`, result.error)
    return null
  }
  return result.data ?? null
}

// Check if backend is available
export function useBackendStatus() {
  const { data, error, isLoading } = useSWR(
    "backend-health",
    async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/health`, {
          method: "GET",
          signal: AbortSignal.timeout(5000),
        })
        if (!response.ok) return { connected: false }
        const data = await response.json()
        return { connected: true, ...data }
      } catch {
        return { connected: false }
      }
    },
    { refreshInterval: 10000, revalidateOnFocus: false },
  )

  return {
    isConnected: data?.connected ?? false,
    exchangesConnected: data?.exchanges_connected ?? 0,
    modelsRegistered: data?.models_registered ?? 0,
    isLoading,
    error,
  }
}

// Agent status from backend
export function useAgentStatus(agentId: string, enabled = true) {
  const { data, error, isLoading, mutate } = useSWR(
    enabled ? `agent-status-${agentId}` : null,
    async () => {
      const result = await getAgent(agentId)
      if (result.error || !result.data) return null
      return result.data.status ?? null
    },
    { refreshInterval: 5000 },
  )

  return {
    status: data,
    isLoading,
    error,
    refresh: mutate,
  }
}

// Positions data
export function useAgentPositions(agentId: string, enabled = true) {
  const { data, error, isLoading, mutate } = useSWR(
    enabled ? `agent-positions-${agentId}` : null,
    async () => {
      const result = await getAgentPositions(agentId)
      if (result.error || !result.data) return []
      return result.data.positions.map((p) => ({
        ...p,
        timestamp: new Date(p.timestamp),
      })) as Position[]
    },
    { refreshInterval: 3000 },
  )

  return {
    positions: data ?? [],
    isLoading,
    error,
    refresh: mutate,
  }
}

// Account balance
export function useAgentBalance(agentId: string, enabled = true) {
  const { data, error, isLoading, mutate } = useSWR(
    enabled ? `agent-balance-${agentId}` : null,
    async () => {
      const result = await getAgentBalance(agentId)
      if (result.error || !result.data) return null
      // Normalize snake_case to camelCase
      const raw = result.data as any
      return {
        totalBalance: raw.total_balance ?? raw.totalBalance ?? 0,
        availableBalance: raw.available_balance ?? raw.availableBalance ?? 0,
        usedMargin: raw.used_margin ?? raw.usedMargin ?? 0,
        unrealizedPnl: raw.unrealized_pnl ?? raw.unrealizedPnl ?? 0,
        realizedPnl: raw.realized_pnl ?? raw.realizedPnl ?? 0,
        todayPnl: raw.today_pnl ?? raw.todayPnl ?? 0,
        weekPnl: raw.week_pnl ?? raw.weekPnl ?? 0,
        monthPnl: raw.month_pnl ?? raw.monthPnl ?? 0,
      } as AccountBalance
    },
    { refreshInterval: 5000 },
  )

  return {
    balance: data,
    isLoading,
    error,
    refresh: mutate,
  }
}

// Conversation history
export function useAgentConversations(agentId: string, enabled = true) {
  const { data, error, isLoading, mutate } = useSWR(
    enabled ? `agent-conversations-${agentId}` : null,
    async () => {
      const result = await getAgentConversations(agentId)
      if (result.error || !result.data) return []
      return result.data.conversations.map((c) => ({
        ...c,
        timestamp: new Date(c.timestamp),
        toolCall: c.toolCall ? { ...c.toolCall, timestamp: new Date(c.timestamp) } : undefined,
      })) as ConversationMessage[]
    },
    { refreshInterval: 5000 },
  )

  return {
    conversations: data ?? [],
    isLoading,
    error,
    refresh: mutate,
  }
}

// Tool calls history
export function useAgentToolCalls(agentId: string, enabled = true) {
  const { data, error, isLoading, mutate } = useSWR(
    enabled ? `agent-toolcalls-${agentId}` : null,
    async () => {
      const result = await getAgentToolCalls(agentId)
      if (result.error || !result.data) return []
      return result.data.toolCalls.map((t) => ({
        ...t,
        timestamp: new Date(t.timestamp),
      })) as ToolCall[]
    },
    { refreshInterval: 5000 },
  )

  return {
    toolCalls: data ?? [],
    isLoading,
    error,
    refresh: mutate,
  }
}

// Orders
export function useAgentOrders(agentId: string, enabled = true) {
  const { data, error, isLoading, mutate } = useSWR(
    enabled ? `agent-orders-${agentId}` : null,
    async () => {
      const result = await getAgentOrders(agentId)
      if (result.error || !result.data) return []
      return result.data.orders
    },
    { refreshInterval: 5000 },
  )

  return {
    orders: data ?? [],
    isLoading,
    error,
    refresh: mutate,
  }
}

// Profit history
export function useAgentProfitHistory(agentId: string, days = 30, enabled = true) {
  const { data, error, isLoading, mutate } = useSWR(
    enabled ? `agent-profit-${agentId}-${days}` : null,
    async () => {
      const result = await getAgentProfitHistory(agentId, days)
      if (result.error || !result.data) return []
      return result.data.profitHistory as ProfitDataPoint[]
    },
    { refreshInterval: 60000 }, // Refresh every minute
  )

  return {
    profitHistory: data ?? [],
    isLoading,
    error,
    refresh: mutate,
  }
}

// Signals
export function useAgentSignals(agentId: string, enabled = true) {
  const { data, error, isLoading, mutate } = useSWR(
    enabled ? `agent-signals-${agentId}` : null,
    async () => {
      const result = await getAgentSignals(agentId)
      if (result.error || !result.data) return []
      return result.data.signals
    },
    { refreshInterval: 5000 },
  )

  return {
    signals: data ?? [],
    isLoading,
    error,
    refresh: mutate,
  }
}

// Logs
export function useAgentLogs(agentId: string, enabled = true) {
  const { data, error, isLoading, mutate } = useSWR(
    enabled ? `agent-logs-${agentId}` : null,
    async () => {
      const result = await getAgentLogs(agentId)
      if (result.error || !result.data) return []
      return result.data.logs
    },
    { refreshInterval: 3000 },
  )

  return {
    logs: data ?? [],
    isLoading,
    error,
    refresh: mutate,
  }
}

// Ticker data
export function useTicker(exchangeId: string, symbol: string, enabled = true) {
  const { data, error, isLoading, mutate } = useSWR(
    enabled && exchangeId && symbol ? `ticker-${exchangeId}-${symbol}` : null,
    async () => {
      const result = await getTicker(exchangeId, symbol)
      if (result.error || !result.data) return null
      return result.data.ticker
    },
    { refreshInterval: 2000 },
  )

  return {
    ticker: data,
    isLoading,
    error,
    refresh: mutate,
  }
}

// Indicators data
export function useIndicators(
  exchangeId: string,
  symbol: string,
  timeframe: string,
  indicators: string[],
  enabled = true,
) {
  const { data, error, isLoading, mutate } = useSWR(
    enabled && exchangeId && symbol ? `indicators-${exchangeId}-${symbol}-${timeframe}` : null,
    async () => {
      const result = await getIndicators(exchangeId, symbol, timeframe, indicators)
      if (result.error || !result.data) return null
      return result.data.indicators
    },
    { refreshInterval: 10000 },
  )

  return {
    indicators: data,
    isLoading,
    error,
    refresh: mutate,
  }
}
