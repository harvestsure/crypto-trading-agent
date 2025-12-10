import { create } from "zustand"
import * as api from "@/lib/api"
import { toast } from "sonner"

interface AppState {
  // Collections
  models: Array<{
    id: string
    name: string
    provider?: string
    model?: string
    status?: string
  }>

  exchanges: Array<{
    id: string
    name: string
    exchange?: string
    status?: string
  }>

  agents: Array<{
    id: string
    name: string
    modelId: string
    exchangeId: string
    symbol?: string
    timeframe?: string
    status?: string
    performance?: { total_trades?: number; win_rate?: number; pnl?: number }
  }>

  // Fetchers
  fetchModels: () => Promise<void>
  fetchExchanges: () => Promise<void>
  fetchAgents: () => Promise<void>

  // Loading states
  isCreatingModel: boolean
  isCreatingExchange: boolean
  isCreatingAgent: boolean

  // API action wrappers that return success/error
  createModel: (model: {
    name: string
    provider: string
    apiKey: string
    baseUrl?: string
    model: string
  }) => Promise<{ success: boolean; error?: string }>

  updateModel: (id: string, data: { status?: string }) => Promise<{ success: boolean; error?: string }>

  deleteModel: (id: string) => Promise<{ success: boolean; error?: string }>

  createExchange: (exchange: {
    name: string
    exchange: string
    apiKey: string
    secretKey: string
    passphrase?: string
    testnet: boolean
  }) => Promise<{ success: boolean; error?: string }>

  updateExchange: (id: string, data: { status?: string }) => Promise<{ success: boolean; error?: string }>

  deleteExchange: (id: string) => Promise<{ success: boolean; error?: string }>

  createAgent: (agent: {
    name: string
    modelId: string
    exchangeId: string
    symbol: string
    timeframe: string
    indicators: string[]
    prompt: string
  }) => Promise<{ success: boolean; error?: string }>

  updateAgent: (id: string, data: { status?: string }) => Promise<{ success: boolean; error?: string }>

  deleteAgent: (id: string) => Promise<{ success: boolean; error?: string }>

  startAgent: (id: string) => Promise<{ success: boolean; error?: string }>

  stopAgent: (id: string) => Promise<{ success: boolean; error?: string }>
}

export const useAppStore = create<AppState>()((set) => ({
  // Collections
  models: [],
  exchanges: [],
  agents: [],

  // Fetchers
  fetchModels: async () => {
    const result = await api.getModels()
    if (result.error) {
      console.error("Failed to fetch models:", result.error)
      return
    }
    const payload = result.data
    if (!payload) return
    const list = Array.isArray(payload) ? payload : ((payload as any).models ?? [])
    if (!Array.isArray(list)) return
    set({
      models: list.map((m: any) => ({
        id: m.id,
        name: m.name,
        provider: m.provider,
        model: m.model,
        status: m.status,
      })),
    })
  },
  fetchExchanges: async () => {
    const result = await api.getExchanges()
    if (result.error) {
      console.error("Failed to fetch exchanges:", result.error)
      return
    }
    const payload = result.data
    if (!payload) return
    const list = Array.isArray(payload) ? payload : ((payload as any).exchanges ?? [])
    if (!Array.isArray(list)) return
    set({ exchanges: list.map((e: any) => ({ id: e.id, name: e.name, exchange: e.exchange, status: e.status })) })
  },
  fetchAgents: async () => {
    const result = await api.getAgents()
    if (result.error) {
      console.error("Failed to fetch agents:", result.error)
      return
    }
    const payload = result.data
    if (!payload) return
    const list = Array.isArray(payload) ? payload : ((payload as any).agents ?? [])
    if (!Array.isArray(list)) return
    set({
      agents: list.map((a: any) => ({
        id: a.id,
        name: a.name,
        modelId: a.model_id,
        exchangeId: a.exchange_id,
        symbol: a.symbol,
        timeframe: a.timeframe,
        status: a.status,
        performance: a.performance,
      })),
    })
  },
  isCreatingModel: false,
  isCreatingExchange: false,
  isCreatingAgent: false,

  createModel: async (model) => {
    set({ isCreatingModel: true })
    try {
      const result = await api.createModel({
        id: crypto.randomUUID(),
        name: model.name,
        provider: model.provider,
        api_key: model.apiKey,
        base_url: model.baseUrl,
        model: model.model,
      })
      set({ isCreatingModel: false })
      if (result.error) {
        toast.error("Failed to create model", { description: result.error })
        return { success: false, error: result.error }
      }
      toast.success("Model created successfully")
      return { success: true }
    } catch (e) {
      set({ isCreatingModel: false })
      const error = e instanceof Error ? e.message : "Unknown error"
      toast.error("Failed to create model", { description: error })
      return { success: false, error }
    }
  },

  updateModel: async (id, data) => {
    const result = await api.updateModel(id, data)
    if (result.error) {
      toast.error("Failed to update model", { description: result.error })
      return { success: false, error: result.error }
    }
    toast.success("Model updated successfully")
    return { success: true }
  },

  deleteModel: async (id) => {
    const result = await api.deleteModel(id)
    if (result.error) {
      toast.error("Failed to delete model", { description: result.error })
      return { success: false, error: result.error }
    }
    toast.success("Model deleted successfully")
    return { success: true }
  },

  createExchange: async (exchange) => {
    set({ isCreatingExchange: true })
    try {
      // Build api_keys object without empty values
      const api_keys: {
        api_key: string
        secret: string
        passphrase?: string
      } = {
        api_key: exchange.apiKey,
        secret: exchange.secretKey,
      }
      if (exchange.passphrase) api_keys.passphrase = exchange.passphrase

      const result = await api.createExchange({
        id: crypto.randomUUID(),
        name: exchange.name,
        exchange: exchange.exchange,
        api_keys,
        testnet: exchange.testnet,
      })
      set({ isCreatingExchange: false })
      if (result.error) {
        toast.error("Failed to create exchange", { description: result.error })
        return { success: false, error: result.error }
      }
      toast.success("Exchange connected successfully")
      return { success: true }
    } catch (e) {
      set({ isCreatingExchange: false })
      const error = e instanceof Error ? e.message : "Unknown error"
      toast.error("Failed to create exchange", { description: error })
      return { success: false, error }
    }
  },

  updateExchange: async (id, data) => {
    const result = await api.updateExchange(id, data)
    if (result.error) {
      toast.error("Failed to update exchange", { description: result.error })
      return { success: false, error: result.error }
    }
    toast.success("Exchange updated successfully")
    return { success: true }
  },

  deleteExchange: async (id) => {
    const result = await api.deleteExchange(id)
    if (result.error) {
      toast.error("Failed to delete exchange", { description: result.error })
      return { success: false, error: result.error }
    }
    toast.success("Exchange deleted successfully")
    return { success: true }
  },

  createAgent: async (agent) => {
    set({ isCreatingAgent: true })
    try {
      const result = await api.createAgent({
        id: crypto.randomUUID(),
        name: agent.name,
        model_id: agent.modelId,
        exchange_id: agent.exchangeId,
        symbol: agent.symbol,
        timeframe: agent.timeframe,
        indicators: agent.indicators,
        prompt: agent.prompt,
      })
      set({ isCreatingAgent: false })
      if (result.error) {
        toast.error("Failed to create agent", { description: result.error })
        return { success: false, error: result.error }
      }
      toast.success("Agent created successfully")
      return { success: true }
    } catch (e) {
      set({ isCreatingAgent: false })
      const error = e instanceof Error ? e.message : "Unknown error"
      toast.error("Failed to create agent", { description: error })
      return { success: false, error }
    }
  },

  updateAgent: async (id, data) => {
    const result = await api.updateAgent(id, data)
    if (result.error) {
      toast.error("Failed to update agent", { description: result.error })
      return { success: false, error: result.error }
    }
    toast.success("Agent updated successfully")
    return { success: true }
  },

  deleteAgent: async (id) => {
    const result = await api.deleteAgent(id)
    if (result.error) {
      toast.error("Failed to delete agent", { description: result.error })
      return { success: false, error: result.error }
    }
    toast.success("Agent deleted successfully")
    return { success: true }
  },

  startAgent: async (id) => {
    const result = await api.startAgent(id)
    if (result.error) {
      toast.error("Failed to start agent", { description: result.error })
      return { success: false, error: result.error }
    }
    toast.success("Agent started successfully")
    return { success: true }
  },

  stopAgent: async (id) => {
    const result = await api.stopAgent(id)
    if (result.error) {
      toast.error("Failed to stop agent", { description: result.error })
      return { success: false, error: result.error }
    }
    toast.success("Agent stopped successfully")
    return { success: true }
  },
}))
