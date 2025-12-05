"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { TrendingUp, TrendingDown } from "lucide-react"
import { cn } from "@/lib/utils"
import type { ProfitDataPoint } from "@/lib/types"
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid, ReferenceLine } from "recharts"

interface ProfitChartProps {
  data: ProfitDataPoint[]
  title?: string
}

export function ProfitChart({ data, title = "Profit & Loss" }: ProfitChartProps) {
  const latestPnl = data.length > 0 ? data[data.length - 1].pnlPercent : 0
  const isProfitable = latestPnl >= 0

  const formatDate = (timestamp: number) => {
    return new Date(timestamp).toLocaleDateString("en-US", { month: "short", day: "numeric" })
  }

  const formatTooltip = (value: number) => {
    return `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`
  }

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base flex items-center justify-between">
          <span>{title}</span>
          <Badge
            variant={isProfitable ? "default" : "destructive"}
            className={cn(isProfitable && "bg-success text-success-foreground")}
          >
            <span className="flex items-center gap-1">
              {isProfitable ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
              {isProfitable ? "+" : ""}
              {latestPnl.toFixed(2)}%
            </span>
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="h-[250px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="profitGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="hsl(var(--success))" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="hsl(var(--success))" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="lossGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="hsl(var(--destructive))" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="hsl(var(--destructive))" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" opacity={0.5} />
              <XAxis
                dataKey="timestamp"
                tickFormatter={formatDate}
                stroke="hsl(var(--muted-foreground))"
                fontSize={11}
                tickLine={false}
                axisLine={false}
              />
              <YAxis
                tickFormatter={(v) => `${v}%`}
                stroke="hsl(var(--muted-foreground))"
                fontSize={11}
                tickLine={false}
                axisLine={false}
              />
              <Tooltip
                formatter={(value: number) => [formatTooltip(value), "PnL"]}
                labelFormatter={(label) => formatDate(label as number)}
                contentStyle={{
                  backgroundColor: "hsl(var(--card))",
                  border: "1px solid hsl(var(--border))",
                  borderRadius: "8px",
                  fontSize: "12px",
                }}
              />
              <ReferenceLine y={0} stroke="hsl(var(--muted-foreground))" strokeDasharray="3 3" />
              <Area
                type="monotone"
                dataKey="pnlPercent"
                stroke={isProfitable ? "hsl(var(--success))" : "hsl(var(--destructive))"}
                strokeWidth={2}
                fill={isProfitable ? "url(#profitGradient)" : "url(#lossGradient)"}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  )
}
