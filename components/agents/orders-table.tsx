"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { cn } from "@/lib/utils"

interface Order {
  id: string
  timestamp: Date
  symbol: string
  side: "buy" | "sell"
  type: "market" | "limit" | "stop_loss" | "take_profit"
  amount: number
  price: number
  status: "filled" | "pending" | "canceled"
  pnl?: number
}

interface OrdersTableProps {
  agentId: string
}

export function OrdersTable({ agentId }: OrdersTableProps) {
  const [orders, setOrders] = useState<Order[]>([])

  useEffect(() => {
    // Generate mock orders
    const mockOrders: Order[] = [
      {
        id: "1",
        timestamp: new Date(Date.now() - 1800000),
        symbol: "BTC/USDT",
        side: "buy",
        type: "market",
        amount: 0.05,
        price: 42850,
        status: "filled",
        pnl: 125.5,
      },
      {
        id: "2",
        timestamp: new Date(Date.now() - 3600000),
        symbol: "BTC/USDT",
        side: "sell",
        type: "take_profit",
        amount: 0.03,
        price: 43200,
        status: "filled",
        pnl: 89.25,
      },
      {
        id: "3",
        timestamp: new Date(Date.now() - 5400000),
        symbol: "BTC/USDT",
        side: "buy",
        type: "limit",
        amount: 0.02,
        price: 42500,
        status: "pending",
      },
      {
        id: "4",
        timestamp: new Date(Date.now() - 7200000),
        symbol: "BTC/USDT",
        side: "sell",
        type: "stop_loss",
        amount: 0.04,
        price: 42000,
        status: "canceled",
      },
      {
        id: "5",
        timestamp: new Date(Date.now() - 9000000),
        symbol: "BTC/USDT",
        side: "buy",
        type: "market",
        amount: 0.06,
        price: 41800,
        status: "filled",
        pnl: -45.3,
      },
    ]

    setOrders(mockOrders)
  }, [agentId])

  const formatType = (type: Order["type"]) => {
    return type.replace("_", " ").replace(/\b\w/g, (l) => l.toUpperCase())
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Order History</CardTitle>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Time</TableHead>
              <TableHead>Side</TableHead>
              <TableHead>Type</TableHead>
              <TableHead>Amount</TableHead>
              <TableHead>Price</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="text-right">PnL</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {orders.map((order) => (
              <TableRow key={order.id}>
                <TableCell className="text-muted-foreground">{order.timestamp.toLocaleTimeString()}</TableCell>
                <TableCell>
                  <Badge
                    variant="secondary"
                    className={cn(
                      order.side === "buy" ? "bg-success/20 text-success" : "bg-destructive/20 text-destructive",
                    )}
                  >
                    {order.side.toUpperCase()}
                  </Badge>
                </TableCell>
                <TableCell>{formatType(order.type)}</TableCell>
                <TableCell>{order.amount}</TableCell>
                <TableCell>${order.price.toLocaleString()}</TableCell>
                <TableCell>
                  <Badge
                    variant={
                      order.status === "filled" ? "default" : order.status === "pending" ? "secondary" : "outline"
                    }
                  >
                    {order.status}
                  </Badge>
                </TableCell>
                <TableCell
                  className={cn(
                    "text-right font-medium",
                    order.pnl && order.pnl > 0 && "text-success",
                    order.pnl && order.pnl < 0 && "text-destructive",
                  )}
                >
                  {order.pnl ? `${order.pnl > 0 ? "+" : ""}$${order.pnl.toFixed(2)}` : "-"}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>

        {orders.length === 0 && <p className="text-center text-sm text-muted-foreground py-8">No orders placed yet</p>}
      </CardContent>
    </Card>
  )
}
