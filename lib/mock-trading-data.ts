/**
 * Mock Trading Data Generator
 * Generates realistic trading actions for demo and testing
 */

import type { TradingAction } from "@/components/agents/action-history"

const SYMBOLS = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT"]

const REASONING_TEMPLATES = {
  LONG: [
    "Strong bullish momentum confirmed by MACD crossover. RSI at 45 showing room for upside. Breaking above EMA20 with increasing volume.",
    "Bullish divergence on RSI. Price bouncing off lower Bollinger Band. ADX showing strengthening uptrend.",
    "Golden cross forming with EMA50 crossing above EMA200. Volume increasing on up moves. Strong support at current level.",
    "Oversold conditions on multiple timeframes. Stochastic showing bullish crossover. Price above VWAP indicating strength.",
  ],
  SHORT: [
    "Bearish MACD histogram divergence. RSI showing overbought at 72. Price rejected at upper Bollinger Band.",
    "Death cross forming with EMAs turning bearish. Declining volume on rallies suggesting weak momentum.",
    "Overbought conditions on RSI and Stochastic. Price testing resistance with bearish candlestick pattern.",
    "Negative ADX reading with -DI dominating. Breaking below key support level with high volume.",
  ],
  CLOSE_LONG: [
    "Taking profit at resistance level. RSI showing bearish divergence. Good risk/reward achieved.",
    "Target reached with 2:1 risk/reward. Momentum slowing, securing gains at current level.",
    "Trailing stop hit as price retraces. Locking in profits after strong upward move.",
  ],
  CLOSE_SHORT: [
    "Covering short at support level. Risk/reward target achieved. Momentum shifting.",
    "Strong buying pressure emerging. Securing short profits before potential reversal.",
    "Price showing signs of exhaustion. Closing short position with satisfactory gains.",
  ],
  HOLD: [
    "No clear signal at current levels. Waiting for better entry point with improved risk/reward.",
    "Market in consolidation phase. RSI neutral at 52. Waiting for trend confirmation.",
    "Conflicting signals from indicators. Better to stay on sidelines until clarity emerges.",
    "Insufficient momentum for entry. Choppy price action suggests range-bound market.",
  ],
}

function getRandomItem<T>(array: T[]): T {
  return array[Math.floor(Math.random() * array.length)]
}

function getRandomAction(): TradingAction["action"] {
  const actions: TradingAction["action"][] = ["LONG", "SHORT", "CLOSE_LONG", "CLOSE_SHORT", "HOLD"]
  const weights = [30, 25, 15, 15, 15] // Weighted probabilities

  const random = Math.random() * 100
  let sum = 0

  for (let i = 0; i < weights.length; i++) {
    sum += weights[i]
    if (random <= sum) {
      return actions[i]
    }
  }

  return "HOLD"
}

function generatePrice(basePrice: number): number {
  const variance = basePrice * 0.02 // 2% variance
  return Math.round((basePrice + (Math.random() - 0.5) * variance) * 100) / 100
}

export function generateMockTradingAction(
  id: string,
  symbol?: string,
  timestamp?: number,
): TradingAction {
  const action = getRandomAction()
  const actionSymbol = symbol ?? getRandomItem(SYMBOLS)
  const basePrice = actionSymbol.includes("BTC")
    ? 43000
    : actionSymbol.includes("ETH")
    ? 2200
    : actionSymbol.includes("SOL")
    ? 95
    : 320

  const price = generatePrice(basePrice)
  const confidence = Math.random() * 0.4 + 0.5 // 0.5 to 0.9
  const reasoning = getRandomItem(REASONING_TEMPLATES[action])

  const tradingAction: TradingAction = {
    id,
    timestamp: timestamp ?? Date.now(),
    action,
    symbol: actionSymbol,
    confidence,
    reasoning,
    price,
  }

  // Add position details for LONG/SHORT actions
  if (action === "LONG" || action === "SHORT") {
    tradingAction.positionSize = Math.floor(Math.random() * 15) + 5 // 5-20%

    if (action === "LONG") {
      tradingAction.stopLoss = Math.round(price * 0.97 * 100) / 100 // 3% stop loss
      tradingAction.takeProfit = Math.round(price * 1.06 * 100) / 100 // 6% take profit
    } else {
      tradingAction.stopLoss = Math.round(price * 1.03 * 100) / 100
      tradingAction.takeProfit = Math.round(price * 0.94 * 100) / 100
    }
  }

  // Randomly assign execution status (70% executed for non-HOLD)
  if (action !== "HOLD") {
    const shouldExecute = Math.random() > 0.3

    if (shouldExecute) {
      const pnl = (Math.random() - 0.4) * 500 // Slightly positive bias
      const pnlPercent = (pnl / (price * (tradingAction.positionSize ?? 10) * 0.01)) * 100

      tradingAction.result = {
        status: "executed",
        pnl: Math.round(pnl * 100) / 100,
        pnlPercent: Math.round(pnlPercent * 100) / 100,
      }
    } else {
      tradingAction.result = {
        status: "pending",
      }
    }
  }

  return tradingAction
}

export function generateMockTradingActions(count: number, symbol?: string): TradingAction[] {
  const actions: TradingAction[] = []
  const now = Date.now()

  for (let i = 0; i < count; i++) {
    // Space out actions over time (random interval between 30 min and 6 hours)
    const timeOffset = Math.floor(Math.random() * (6 * 60 * 60 * 1000 - 30 * 60 * 1000)) + 30 * 60 * 1000
    const timestamp = now - i * timeOffset

    actions.push(generateMockTradingAction(`action_${timestamp}_${i}`, symbol, timestamp))
  }

  return actions.sort((a, b) => b.timestamp - a.timestamp)
}

/**
 * Generate a realistic sequence of trading actions for backtesting visualization
 */
export function generateTradingSequence(symbol: string, days: number = 7): TradingAction[] {
  const actions: TradingAction[] = []
  const now = Date.now()
  const msPerDay = 24 * 60 * 60 * 1000

  // Generate 3-6 actions per day
  for (let day = 0; day < days; day++) {
    const actionsPerDay = Math.floor(Math.random() * 4) + 3

    for (let i = 0; i < actionsPerDay; i++) {
      const dayOffset = day * msPerDay
      const timeWithinDay = Math.floor(Math.random() * msPerDay)
      const timestamp = now - dayOffset - timeWithinDay

      actions.push(generateMockTradingAction(`seq_${timestamp}_${day}_${i}`, symbol, timestamp))
    }
  }

  return actions.sort((a, b) => b.timestamp - a.timestamp)
}
