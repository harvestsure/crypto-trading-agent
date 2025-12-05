import { create } from "zustand"
import { persist } from "zustand/middleware"
import type { AIModel, Exchange, TradingAgent, Order } from "./types"

interface AppState {
  models: AIModel[]
  exchanges: Exchange[]
  agents: TradingAgent[]
  orders: Order[]

  addModel: (model: AIModel) => void
  updateModel: (id: string, model: Partial<AIModel>) => void
  deleteModel: (id: string) => void

  addExchange: (exchange: Exchange) => void
  updateExchange: (id: string, exchange: Partial<Exchange>) => void
  deleteExchange: (id: string) => void

  addAgent: (agent: TradingAgent) => void
  updateAgent: (id: string, agent: Partial<TradingAgent>) => void
  deleteAgent: (id: string) => void

  addOrder: (order: Order) => void
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      models: [],
      exchanges: [],
      agents: [],
      orders: [],

      addModel: (model) => set((state) => ({ models: [...state.models, model] })),
      updateModel: (id, model) =>
        set((state) => ({
          models: state.models.map((m) => (m.id === id ? { ...m, ...model } : m)),
        })),
      deleteModel: (id) =>
        set((state) => ({
          models: state.models.filter((m) => m.id !== id),
        })),

      addExchange: (exchange) => set((state) => ({ exchanges: [...state.exchanges, exchange] })),
      updateExchange: (id, exchange) =>
        set((state) => ({
          exchanges: state.exchanges.map((e) => (e.id === id ? { ...e, ...exchange } : e)),
        })),
      deleteExchange: (id) =>
        set((state) => ({
          exchanges: state.exchanges.filter((e) => e.id !== id),
        })),

      addAgent: (agent) => set((state) => ({ agents: [...state.agents, agent] })),
      updateAgent: (id, agent) =>
        set((state) => ({
          agents: state.agents.map((a) => (a.id === id ? { ...a, ...agent } : a)),
        })),
      deleteAgent: (id) =>
        set((state) => ({
          agents: state.agents.filter((a) => a.id !== id),
        })),

      addOrder: (order) => set((state) => ({ orders: [...state.orders, order] })),
    }),
    {
      name: "crypto-agent-storage",
    },
  ),
)
