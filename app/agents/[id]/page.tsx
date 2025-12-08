import { use } from "react"
import AgentDetailClient from "./agent-detail-client"

interface PageProps {
  params: Promise<{ id: string }>
}

export default function AgentDetailPage({ params }: PageProps) {
  const { id } = use(params)
  return <AgentDetailClient id={id} />
}
