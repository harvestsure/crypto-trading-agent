"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { TrendingUp, TrendingDown } from "lucide-react"
import { cn } from "@/lib/utils"
import type { ProfitDataPoint } from "@/lib/types"
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid, ReferenceLine } from "recharts"
import { useTheme } from "next-themes"

interface ProfitChartProps {
  data: ProfitDataPoint[]
  title?: string
}

export function ProfitChart({ data, title = "Profit & Loss" }: ProfitChartProps) {
  const { resolvedTheme } = useTheme()
  const isDark = resolvedTheme === "dark"
  
  const latestPnl = data.length > 0 ? data[data.length - 1].pnlPercent : 0
  const isProfitable = latestPnl >= 0

  const formatDate = (timestamp: number) => {
    return new Date(timestamp).toLocaleDateString("en-US", { month: "short", day: "numeric" })
  }

  const formatTooltip = (value: number) => {
    return `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`
  }

  // 主题相关的颜色值
  const chartColors = {
    success: isDark ? "#b3ff00" : "#10b981",
    destructive: isDark ? "#ff6b6b" : "#ef4444",
    muted: isDark ? "#404040" : "#c7d2e0",
    mutedForeground: isDark ? "#a3a3a3" : "#64748b",
    card: isDark ? "#262626" : "#ffffff",
    foreground: isDark ? "#f5f5f5" : "#1f2937",
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
        <div className="h-60 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ top: 10, right: 10, left: 0, bottom: 20 }}>
              <defs>
                <linearGradient id="profitGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={chartColors.success} stopOpacity={0.4} />
                  <stop offset="95%" stopColor={chartColors.success} stopOpacity={0.1} />
                </linearGradient>
                <linearGradient id="lossGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={chartColors.destructive} stopOpacity={0.4} />
                  <stop offset="95%" stopColor={chartColors.destructive} stopOpacity={0.1} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke={chartColors.muted} opacity={0.4} />
              <XAxis
                dataKey="timestamp"
                tickFormatter={formatDate}
                stroke={chartColors.mutedForeground}
                fontSize={12}
                tick={{ fill: chartColors.mutedForeground }}
                tickLine={{ stroke: chartColors.muted }}
                axisLine={{ stroke: chartColors.muted }}
              />
              <YAxis
                tickFormatter={(v) => `${v}%`}
                stroke={chartColors.mutedForeground}
                fontSize={12}
                tick={{ fill: chartColors.mutedForeground }}
                tickLine={{ stroke: chartColors.muted }}
                axisLine={{ stroke: chartColors.muted }}
              />
              <Tooltip
                formatter={(value: number) => [formatTooltip(value), "PnL"]}
                labelFormatter={(label) => formatDate(label as number)}
                contentStyle={{
                  backgroundColor: chartColors.card,
                  border: `2px solid ${chartColors.success}`,
                  borderRadius: "8px",
                  fontSize: "12px",
                  color: chartColors.foreground,
                  boxShadow: "0 4px 12px rgba(0, 0, 0, 0.5)",
                }}
              />
              <ReferenceLine y={0} stroke={chartColors.mutedForeground} strokeDasharray="5 5" strokeOpacity={0.6} />
              <Area
                type="monotone"
                dataKey="pnlPercent"
                stroke={isProfitable ? chartColors.success : chartColors.destructive}
                strokeWidth={3}
                fill={isProfitable ? "url(#profitGradient)" : "url(#lossGradient)"}
                isAnimationActive={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  )
}
