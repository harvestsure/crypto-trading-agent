"use client"

import useSWR from "swr"
import * as api from "@/lib/api"
import type { AIModel, Exchange, TradingAgent } from "@/lib/types"

// Transform backend response to frontend types
function transformModel(data: {
  id: string
  name: string
  provider: string
  model: string
  base_url?: string
  status: string
  created_at: string
}): AIModel {
  return {
    id: data.id,
    name: data.name,
    provider: data.provider as AIModel["provider"],
    model: data.model,
    apiKey: "***", // Hidden for security
    baseUrl: data.base_url,
    status: data.status as AIModel["status"],
    createdAt: new Date(data.created_at),
  }
}

function transformExchange(data: {
  id: string
  name: string
  exchange: string
  testnet: boolean
  status: string
  created_at: string
}): Exchange {
  return {
    id: data.id,
    name: data.name,
    exchange: data.exchange as Exchange["exchange"],
    apiKey: "***",
    secretKey: "***",
    testnet: data.testnet,
    status: data.status as Exchange["status"],
    createdAt: new Date(data.created_at),
  }
}

function transformAgent(data: {
  id: string
  name: string
  model_id: string
  exchange_id: string
  symbol: string
  timeframe: string
  indicators: string[]
  prompt: string
  status: string
  created_at: string
  performance?: {
    total_trades: number
    win_rate: number
    pnl: number
  }
}): TradingAgent {
  return {
    id: data.id,
    name: data.name,
    modelId: data.model_id,
    exchangeId: data.exchange_id,
    symbol: data.symbol,
    timeframe: data.timeframe as TradingAgent["timeframe"],
    indicators: data.indicators,
    prompt: data.prompt,
    status: (data.status === "running"
      ? "running"
      : data.status === "paused"
        ? "paused"
        : "stopped") as TradingAgent["status"],
    createdAt: new Date(data.created_at),
    performance: data.performance
      ? {
          totalTrades: data.performance.total_trades,
          winRate: data.performance.win_rate,
          pnl: data.performance.pnl,
        }
      : undefined,
  }
}

// SWR fetcher functions
async function fetchModels(): Promise<AIModel[]> {
  const result = await api.getModels()
  if (result.error || !result.data) return []
  return result.data.models.map(transformModel)
}

async function fetchExchanges(): Promise<Exchange[]> {
  const result = await api.getExchanges()
  if (result.error || !result.data) return []
  return result.data.exchanges.map(transformExchange)
}

async function fetchAgents(): Promise<TradingAgent[]> {
  const result = await api.getAgents()
  if (result.error || !result.data) return []
  return result.data.agents.map(transformAgent)
}

// SWR Hooks
export function useModels() {
  const { data, error, isLoading, mutate } = useSWR("models", fetchModels, {
    refreshInterval: 10000, // Refresh every 10 seconds
    revalidateOnFocus: true,
  })

  return {
    models: data ?? [],
    isLoading,
    isError: !!error,
    mutate,
  }
}

export function useExchanges() {
  const { data, error, isLoading, mutate } = useSWR("exchanges", fetchExchanges, {
    refreshInterval: 10000,
    revalidateOnFocus: true,
  })

  return {
    exchanges: data ?? [],
    isLoading,
    isError: !!error,
    mutate,
  }
}

export function useAgents() {
  const { data, error, isLoading, mutate } = useSWR("agents", fetchAgents, {
    refreshInterval: 5000, // Refresh every 5 seconds for more real-time agent status
    revalidateOnFocus: true,
  })

  return {
    agents: data ?? [],
    isLoading,
    isError: !!error,
    mutate,
  }
}

// Single item hooks
export function useModel(id: string) {
  const { data, error, isLoading, mutate } = useSWR(id ? `model-${id}` : null, async () => {
    const result = await api.getModel(id)
    if (result.error || !result.data) return null
    return transformModel(result.data)
  })

  return { model: data, isLoading, isError: !!error, mutate }
}

export function useExchange(id: string) {
  const { data, error, isLoading, mutate } = useSWR(id ? `exchange-${id}` : null, async () => {
    const result = await api.getExchange(id)
    if (result.error || !result.data) return null
    return transformExchange(result.data)
  })

  return { exchange: data, isLoading, isError: !!error, mutate }
}

export function useAgent(id: string) {
  const { data, error, isLoading, mutate } = useSWR(
    id ? `agent-${id}` : null,
    async () => {
      const result = await api.getAgent(id)
      if (result.error || !result.data) return null
      return transformAgent(result.data)
    },
    { refreshInterval: 3000 },
  )

  return { agent: data, isLoading, isError: !!error, mutate }
}
