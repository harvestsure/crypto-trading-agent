import { NextRequest, NextResponse } from "next/server"
import { calculateAllIndicators } from "@/lib/indicators"

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const { klines } = body

    if (!klines || !Array.isArray(klines) || klines.length === 0) {
      return NextResponse.json({ error: "Invalid klines data" }, { status: 400 })
    }

    // Calculate all technical indicators
    const indicators = calculateAllIndicators(klines)

    return NextResponse.json({
      success: true,
      indicators,
      timestamp: Date.now(),
    })
  } catch (error) {
    console.error("[v0] Indicators calculation error:", error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Failed to calculate indicators" },
      { status: 500 }
    )
  }
}
