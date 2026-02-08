import { NextRequest, NextResponse } from "next/server"

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

export async function GET(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams
    const exchangeId = searchParams.get("exchangeId")
    const symbol = searchParams.get("symbol")
    const timeframe = searchParams.get("timeframe")
    const limit = searchParams.get("limit") || "500"

    if (!exchangeId || !symbol || !timeframe) {
      return NextResponse.json(
        { error: "Missing required parameters: exchangeId, symbol, timeframe" },
        { status: 400 }
      )
    }

    // Forward request to Python backend
    const backendUrl = `${BACKEND_URL}/api/klines?exchange_id=${exchangeId}&symbol=${symbol}&timeframe=${timeframe}&limit=${limit}`
    
    const response = await fetch(backendUrl, {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
        Authorization: request.headers.get("Authorization") || "",
      },
    })

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: "Backend error" }))
      return NextResponse.json({ error: error.detail }, { status: response.status })
    }

    const data = await response.json()
    return NextResponse.json(data)
  } catch (error) {
    console.error("[v0] Klines API error:", error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Failed to fetch klines" },
      { status: 500 }
    )
  }
}
