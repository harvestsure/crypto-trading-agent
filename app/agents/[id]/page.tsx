import { use } from "react"
import { ProtectedRoute } from "@/components/auth/protected-route"
import AgentDetailClient from "./agent-detail-client"

interface PageProps {
  params: Promise<{ id: string }>
}

export default function AgentDetailPage({ params }: PageProps) {
  const { id } = use(params)
  return (
    <ProtectedRoute>
      <AgentDetailClient id={id} />
    </ProtectedRoute>
  )
}
