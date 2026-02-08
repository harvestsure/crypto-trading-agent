import { NextRequest, NextResponse } from "next/server"
import { generateText } from "ai"
import { calculateAllIndicators, generateMarketAnalysis, type KlineData } from "@/lib/indicators"

/**
 * AI Trading Analysis API
 * Analyzes market data with technical indicators and generates trading decisions
 */

const TRADING_SYSTEM_PROMPT = `You are an expert cryptocurrency trading AI agent with deep knowledge of technical analysis and risk management.

Your role is to analyze market data and technical indicators to make informed trading decisions. You MUST respond with a valid JSON object containing your trading decision.

Available Actions:
- LONG: Open a long position (buy)
- SHORT: Open a short position (sell)
- CLOSE_LONG: Close an existing long position
- CLOSE_SHORT: Close an existing short position
- HOLD: Do nothing, wait for better conditions

Your response MUST be a valid JSON object with this exact structure:
{
  "action": "LONG" | "SHORT" | "CLOSE_LONG" | "CLOSE_SHORT" | "HOLD",
  "confidence": 0.0 to 1.0,
  "reasoning": "detailed explanation of your decision",
  "stopLoss": price level for stop loss (optional),
  "takeProfit": price level for take profit (optional),
  "positionSize": recommended position size as percentage (1-100)
}

Consider:
- Multiple timeframe analysis
- Risk/reward ratios
- Market trends and momentum
- Support and resistance levels
- Volume analysis
- Avoid overtrading - only trade high-probability setups
- Always include stop loss levels for risk management`

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const {
      symbol,
      timeframe,
      klines,
      customPrompt,
      riskTolerance = "medium",
    }: {
      symbol: string
      timeframe: string
      klines: KlineData[]
      customPrompt?: string
      riskTolerance?: "low" | "medium" | "high"
    } = body

    // Validate input
    if (!symbol || !timeframe || !klines || klines.length === 0) {
      return NextResponse.json({ error: "Missing required parameters" }, { status: 400 })
    }

    // Calculate all technical indicators
    const indicators = calculateAllIndicators(klines)

    // Generate market analysis text
    const marketAnalysis = generateMarketAnalysis(klines, indicators)

    // Build the user prompt
    const userPrompt = `
${customPrompt ? `Custom Strategy: ${customPrompt}\n\n` : ''}
Trading Pair: ${symbol}
Timeframe: ${timeframe}
Risk Tolerance: ${riskTolerance}

${marketAnalysis}

Recent Price Action (last 5 candles):
${klines
  .slice(-5)
  .map(
    (k, i) =>
      `${i + 1}. Open: $${k.open.toFixed(2)}, High: $${k.high.toFixed(2)}, Low: $${k.low.toFixed(2)}, Close: $${k.close.toFixed(2)}, Volume: ${k.volume.toFixed(2)}`,
  )
  .join('\n')}

Based on the above technical analysis and market conditions, provide your trading decision as a JSON object.`

    // Call AI model using Vercel AI SDK
    const result = await generateText({
      model: "openai/gpt-4o-mini",
      messages: [
        { role: "system", content: TRADING_SYSTEM_PROMPT },
        { role: "user", content: userPrompt },
      ],
      temperature: 0.3, // Lower temperature for more consistent decisions
      maxTokens: 500,
    })

    // Parse the AI response
    let decision
    try {
      // Extract JSON from markdown code blocks if present
      let textResponse = result.text.trim()
      const jsonMatch = textResponse.match(/```(?:json)?\s*(\{[\s\S]*?\})\s*```/)
      if (jsonMatch) {
        textResponse = jsonMatch[1]
      }

      decision = JSON.parse(textResponse)

      // Validate decision structure
      if (!decision.action || !decision.reasoning) {
        throw new Error("Invalid decision format")
      }

      // Ensure valid action
      const validActions = ["LONG", "SHORT", "CLOSE_LONG", "CLOSE_SHORT", "HOLD"]
      if (!validActions.includes(decision.action)) {
        decision.action = "HOLD"
      }

      // Ensure confidence is between 0 and 1
      if (typeof decision.confidence !== "number") {
        decision.confidence = 0.5
      }
      decision.confidence = Math.max(0, Math.min(1, decision.confidence))

      // Ensure positionSize is valid
      if (typeof decision.positionSize !== "number" || decision.positionSize <= 0) {
        decision.positionSize = riskTolerance === "high" ? 20 : riskTolerance === "low" ? 5 : 10
      }
    } catch (parseError) {
      console.error("[v0] Failed to parse AI decision:", parseError, "Raw response:", result.text)
      // Return a safe default
      decision = {
        action: "HOLD",
        confidence: 0.3,
        reasoning: "Unable to make a confident decision based on current market conditions. Waiting for clearer signals.",
        positionSize: 5,
      }
    }

    return NextResponse.json({
      success: true,
      decision,
      indicators,
      timestamp: Date.now(),
    })
  } catch (error) {
    console.error("[v0] Trading analysis error:", error)
    return NextResponse.json(
      {
        error: error instanceof Error ? error.message : "Analysis failed",
      },
      { status: 500 },
    )
  }
}
