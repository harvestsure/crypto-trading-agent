import { NextRequest, NextResponse } from "next/server"

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

// GET - Fetch trading actions history
export async function GET(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams
    const agentId = searchParams.get("agentId")
    const limit = searchParams.get("limit") || "50"

    if (!agentId) {
      return NextResponse.json({ error: "Missing agentId parameter" }, { status: 400 })
    }

    const backendUrl = `${BACKEND_URL}/api/agents/${agentId}/actions?limit=${limit}`

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
    console.error("[v0] Trading actions fetch error:", error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Failed to fetch trading actions" },
      { status: 500 }
    )
  }
}

// POST - Create new trading action
export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const { agentId, action } = body

    if (!agentId || !action) {
      return NextResponse.json({ error: "Missing required fields" }, { status: 400 })
    }

    const backendUrl = `${BACKEND_URL}/api/agents/${agentId}/actions`

    const response = await fetch(backendUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: request.headers.get("Authorization") || "",
      },
      body: JSON.stringify(action),
    })

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: "Backend error" }))
      return NextResponse.json({ error: error.detail }, { status: response.status })
    }

    const data = await response.json()
    return NextResponse.json(data)
  } catch (error) {
    console.error("[v0] Trading action creation error:", error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Failed to create trading action" },
      { status: 500 }
    )
  }
}
