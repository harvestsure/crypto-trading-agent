import { cn } from "@/lib/utils"
import type { LucideIcon } from "lucide-react"

interface StatsCardProps {
  title: string
  value: string | number
  change?: string
  changeType?: "positive" | "negative" | "neutral"
  icon: LucideIcon
}

export function StatsCard({ title, value, change, changeType = "neutral", icon: Icon }: StatsCardProps) {
  return (
    <div className="group relative rounded-xl border border-border bg-card p-6 transition-all hover:border-primary/30 hover:shadow-md hover:shadow-primary/5">
      <div className="flex items-center justify-between mb-4">
        <span className="text-sm font-medium text-muted-foreground">{title}</span>
        <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-primary/10 transition-all group-hover:bg-primary/15 group-hover:scale-105">
          <Icon className="h-5 w-5 text-primary" />
        </div>
      </div>
      <div className="space-y-1">
        <span className="text-3xl font-bold text-foreground tabular-nums leading-none">{value}</span>
        {change && (
          <div>
            <span
              className={cn(
                "text-sm font-medium inline-block",
                changeType === "positive" && "text-success",
                changeType === "negative" && "text-destructive",
                changeType === "neutral" && "text-muted-foreground",
              )}
            >
              {change}
            </span>
          </div>
        )}
      </div>
    </div>
  )
}
