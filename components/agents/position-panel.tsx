"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { DollarSign, Shield } from "lucide-react"
import { cn } from "@/lib/utils"
import type { Position, AccountBalance } from "@/lib/types"

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

interface PositionPanelProps {
  positions: Position[]
  balance: AccountBalance
  agentId?: string
}

export function PositionPanel({ positions, balance, agentId }: PositionPanelProps) {
  const isProfitToday = balance.todayPnl >= 0
  const [orders, setOrders] = useState<Order[]>([])
  const [orderFilter, setOrderFilter] = useState<"all" | "open" | "closed">("all")

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

  const getFilteredOrders = () => {
    if (orderFilter === "all") return orders
    if (orderFilter === "open") return orders.filter((o) => o.status === "pending")
    return orders.filter((o) => o.status !== "pending")
  }

  const formatType = (type: Order["type"]) => {
    return type.replace("_", " ").replace(/\b\w/g, (l) => l.toUpperCase())
  }

  const filteredOrders = getFilteredOrders()

  return (
    <div className="space-y-4">
      {/* Account Overview */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base flex items-center gap-2">
            <DollarSign className="h-4 w-4" />
            Account Overview
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1">
              <p className="text-xs text-muted-foreground">Total Balance</p>
              <p className="text-xl font-bold text-foreground">
                ${balance.totalBalance.toLocaleString(undefined, { minimumFractionDigits: 2 })}
              </p>
            </div>
            <div className="space-y-1">
              <p className="text-xs text-muted-foreground">Available</p>
              <p className="text-xl font-bold text-foreground">
                ${balance.availableBalance.toLocaleString(undefined, { minimumFractionDigits: 2 })}
              </p>
            </div>
          </div>

          <div className="h-px bg-border" />

          <div className="grid grid-cols-3 gap-3">
            <div className="rounded-lg bg-secondary/50 p-2 text-center">
              <p className="text-xs text-muted-foreground">Today</p>
              <p className={cn("text-sm font-semibold", isProfitToday ? "text-success" : "text-destructive")}>
                {isProfitToday ? "+" : ""}
                {balance.todayPnl.toFixed(2)}%
              </p>
            </div>
            <div className="rounded-lg bg-secondary/50 p-2 text-center">
              <p className="text-xs text-muted-foreground">Week</p>
              <p className={cn("text-sm font-semibold", balance.weekPnl >= 0 ? "text-success" : "text-destructive")}>
                {balance.weekPnl >= 0 ? "+" : ""}
                {balance.weekPnl.toFixed(2)}%
              </p>
            </div>
            <div className="rounded-lg bg-secondary/50 p-2 text-center">
              <p className="text-xs text-muted-foreground">Month</p>
              <p className={cn("text-sm font-semibold", balance.monthPnl >= 0 ? "text-success" : "text-destructive")}>
                {balance.monthPnl >= 0 ? "+" : ""}
                {balance.monthPnl.toFixed(2)}%
              </p>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3 text-sm">
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">Used Margin</span>
              <span className="text-foreground">${balance.usedMargin.toLocaleString()}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">Unrealized PnL</span>
              <span className={cn(balance.unrealizedPnl >= 0 ? "text-success" : "text-destructive")}>
                {balance.unrealizedPnl >= 0 ? "+" : ""}${balance.unrealizedPnl.toLocaleString()}
              </span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Orders */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <Shield className="h-4 w-4" />
            Orders
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3 mb-4">
            <div className="flex gap-2">
              <Button
                variant={orderFilter === "all" ? "default" : "outline"}
                size="sm"
                onClick={() => setOrderFilter("all")}
              >
                All ({orders.length})
              </Button>
              <Button
                variant={orderFilter === "open" ? "default" : "outline"}
                size="sm"
                onClick={() => setOrderFilter("open")}
              >
                Open ({orders.filter((o) => o.status === "pending").length})
              </Button>
              <Button
                variant={orderFilter === "closed" ? "default" : "outline"}
                size="sm"
                onClick={() => setOrderFilter("closed")}
              >
                Closed ({orders.filter((o) => o.status !== "pending").length})
              </Button>
            </div>
          </div>

          {filteredOrders.length === 0 ? (
            <p className="text-center text-sm text-muted-foreground py-8">No orders</p>
          ) : (
            <div className="border rounded-lg overflow-hidden">
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
                  {filteredOrders.map((order) => (
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
                            order.status === "filled"
                              ? "default"
                              : order.status === "pending"
                              ? "secondary"
                              : "outline"
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
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
