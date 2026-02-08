import { use } from "react"
import CompactAgentPage from "./page-compact"

interface PageProps {
  params: Promise<{ id: string }>
}

export default function AgentDetailPage({ params }: PageProps) {
  const { id } = use(params)
  return <CompactAgentPage params={{ id }} />
}
