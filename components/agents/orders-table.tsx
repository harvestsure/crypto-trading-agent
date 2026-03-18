"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Skeleton } from "@/components/ui/skeleton"
import { cn } from "@/lib/utils"
import { useAgentOrders } from "@/hooks/use-agent-data"

interface OrdersTableProps {
  agentId: string
}

const TYPE_LABELS: Record<string, string> = {
  market: "Market",
  limit: "Limit",
  stop: "Stop",
  stop_loss: "Stop Loss",
  take_profit: "Take Profit",
}

export function OrdersTable({ agentId }: OrdersTableProps) {
  const { orders, isLoading } = useAgentOrders(agentId, !!agentId)

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Order History</CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="space-y-1">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-9 w-full" />
            ))}
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Time</TableHead>
                <TableHead>Symbol</TableHead>
                <TableHead>Side</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Amount</TableHead>
                <TableHead>Price</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">PnL</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {orders.map((order: any) => {
                const ts = order.timestamp ? new Date(order.timestamp) : null
                const pnl = order.pnl ?? null
                return (
                  <TableRow key={order.id}>
                    <TableCell className="text-muted-foreground text-xs">
                      {ts ? ts.toLocaleTimeString() : "—"}
                    </TableCell>
                    <TableCell className="font-mono text-xs">{order.symbol ?? "—"}</TableCell>
                    <TableCell>
                      <Badge
                        variant="secondary"
                        className={cn(
                          order.side === "buy"
                            ? "bg-success/20 text-success"
                            : "bg-destructive/20 text-destructive",
                        )}
                      >
                        {(order.side ?? "—").toUpperCase()}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-xs">
                      {TYPE_LABELS[order.type ?? ""] ?? order.type ?? "—"}
                    </TableCell>
                    <TableCell>{order.amount ?? "—"}</TableCell>
                    <TableCell>
                      {order.price != null ? `$${Number(order.price).toLocaleString()}` : "—"}
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant={
                          order.status === "filled"
                            ? "default"
                            : order.status === "pending"
                              ? "secondary"
                              : "outline"
                        }
                      >
                        {order.status ?? "—"}
                      </Badge>
                    </TableCell>
                    <TableCell
                      className={cn(
                        "text-right font-medium text-xs",
                        pnl != null && pnl > 0 && "text-success",
                        pnl != null && pnl < 0 && "text-destructive",
                      )}
                    >
                      {pnl != null
                        ? `${pnl > 0 ? "+" : ""}$${Number(pnl).toFixed(2)}`
                        : "—"}
                    </TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        )}

        {!isLoading && orders.length === 0 && (
          <p className="text-center text-sm text-muted-foreground py-8">No orders placed yet</p>
        )}
      </CardContent>
    </Card>
  )
}
