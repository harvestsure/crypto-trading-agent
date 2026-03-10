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
  positions: Position[];
  balance: AccountBalance;
  agentId?: string;
  pnl?: number;
  totalTrades?: number;
  winRate?: number;
  lastSignal?: { action?: string };
  isProfitable?: boolean;
}


export function PositionPanel({ positions, balance, agentId, pnl, totalTrades, winRate, lastSignal, isProfitable }: PositionPanelProps) {
  const isProfitToday = balance.todayPnl >= 0;
  const [orders, setOrders] = useState<Order[]>([]);
  const [orderFilter, setOrderFilter] = useState<"all" | "open" | "closed">("all");

  // Summary props
  // Use fallback if not provided
  const summaryPnl = typeof pnl === "number" ? pnl : 0;
  const summaryTrades = typeof totalTrades === "number" ? totalTrades : 0;
  const summaryWinRate = typeof winRate === "number" ? winRate : 0;
  const summarySignal = lastSignal?.action ?? "—";
  const summaryIsProfitable = typeof isProfitable === "boolean" ? isProfitable : summaryPnl >= 0;

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
    ];
    setOrders(mockOrders);
  }, [agentId]);

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
    <div>
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base flex items-center gap-2">
            <DollarSign className="h-4 w-4" />
            Account Overview
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Summary Card内容 */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <p className="text-xs text-muted-foreground">PnL</p>
              <p className={cn("text-lg font-bold", summaryIsProfitable ? "text-success" : "text-destructive")}> 
                {summaryIsProfitable ? "+" : ""}{summaryPnl.toFixed(1)}%
              </p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Trades</p>
              <p className="text-lg font-bold text-foreground">{summaryTrades}</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Win Rate</p>
              <p className="text-lg font-bold text-foreground">{summaryWinRate}%</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Signal</p>
              <p className="text-lg font-bold text-foreground capitalize truncate">
                {summarySignal}
              </p>
            </div>
          </div>

          {/* Account Overview内容 */}
          <div className="grid grid-cols-2 gap-4 mt-6">
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
    </div>
  )
}
