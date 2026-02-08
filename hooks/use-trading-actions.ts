/**
 * Trading Actions Hook
 * Manages trading action history from backend
 */

import useSWR from "swr"
import { useState, useCallback } from "react"
import type { TradingAction } from "@/components/agents/action-history"

async function fetcher(url: string) {
  const response = await fetch(url)
  if (!response.ok) {
    throw new Error("Failed to fetch trading actions")
  }
  const data = await response.json()
  return data
}

export interface UseTradingActionsOptions {
  agentId: string
  limit?: number
  autoRefresh?: boolean
  refreshInterval?: number
}

export function useTradingActions(options: UseTradingActionsOptions) {
  const { agentId, limit = 50, autoRefresh = true, refreshInterval = 10000 } = options

  const [isSubmitting, setIsSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)

  // Fetch trading actions from backend
  const {
    data,
    error,
    mutate,
    isLoading,
  } = useSWR<{ actions: TradingAction[] }>(
    agentId ? `/api/trading/actions?agentId=${agentId}&limit=${limit}` : null,
    fetcher,
    {
      refreshInterval: autoRefresh ? refreshInterval : 0,
      revalidateOnFocus: true,
      dedupingInterval: 5000,
    }
  )

  /**
   * Submit a new trading action
   */
  const submitAction = useCallback(
    async (action: Omit<TradingAction, "id" | "timestamp">) => {
      setIsSubmitting(true)
      setSubmitError(null)

      try {
        const response = await fetch("/api/trading/actions", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            agentId,
            action: {
              ...action,
              timestamp: Date.now(),
            },
          }),
        })

        if (!response.ok) {
          const errorData = await response.json()
          throw new Error(errorData.error || "Failed to submit action")
        }

        const result = await response.json()

        // Refresh the list
        mutate()

        console.log("[v0] Trading action submitted successfully:", result)
        return result
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : "Unknown error"
        setSubmitError(errorMessage)
        console.error("[v0] Failed to submit trading action:", errorMessage)
        return null
      } finally {
        setIsSubmitting(false)
      }
    },
    [agentId, mutate]
  )

  return {
    actions: data?.actions || [],
    isLoading,
    error: error?.message || null,
    isSubmitting,
    submitError,
    submitAction,
    refresh: mutate,
  }
}
