"use client"

import { useState } from "react"
import { useExchanges } from "@/hooks/use-data"
import { useAppStore } from "@/lib/store"
import { Sidebar } from "@/components/layout/sidebar"
import { Header } from "@/components/layout/header"
import { CreateExchangeModal } from "@/components/modals/create-exchange-modal"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Plus, MoreVertical, Building2, Trash2, RefreshCw, Loader2, AlertCircle, X } from "lucide-react"
import { cn } from "@/lib/utils"
import { Skeleton } from "@/components/ui/skeleton"

export default function ExchangesPage() {
  const { exchanges, isLoading, mutate } = useExchanges()
  const { updateExchange, deleteExchange } = useAppStore()
  const [isCreateOpen, setIsCreateOpen] = useState(false)
  const [deleteError, setDeleteError] = useState<string | null>(null)

  const handleDelete = async (id: string) => {
    setDeleteError(null)
    const result = await deleteExchange(id)
    if (result.success) {
      mutate()
    } else {
      setDeleteError(result.error || "Failed to delete exchange")
    }
  }

  const handleReconnect = async (id: string) => {
    const result = await updateExchange(id, { status: "connected" })
    if (result.success) {
      mutate()
    }
  }

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="flex-1 pl-64">
        <Header title="Exchanges" description="Manage your exchange connections" />

        <div className="p-6">
          {deleteError && (
            <Alert variant="destructive" className="mb-4">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription className="ml-2 flex items-center justify-between">
                <span>{deleteError}</span>
                <button onClick={() => setDeleteError(null)} className="ml-4 hover:opacity-70">
                  <X className="h-4 w-4" />
                </button>
              </AlertDescription>
            </Alert>
          )}
          <div className="mb-6 flex items-center justify-between">
            <div>
              {isLoading ? (
                <Skeleton className="h-5 w-32" />
              ) : (
                <p className="text-sm text-muted-foreground">
                  {exchanges.length} exchange{exchanges.length !== 1 ? "s" : ""} connected
                </p>
              )}
            </div>
            <Button onClick={() => setIsCreateOpen(true)}>
              <Plus className="mr-2 h-4 w-4" />
              Add Exchange
            </Button>
          </div>

          {isLoading ? (
            <div className="rounded-xl border border-border bg-card p-8">
              <div className="flex items-center justify-center gap-2">
                <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                <span className="text-muted-foreground">Loading exchanges...</span>
              </div>
            </div>
          ) : exchanges.length === 0 ? (
            <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-border bg-card p-12 text-center">
              <Building2 className="h-12 w-12 text-muted-foreground" />
              <h3 className="mt-4 text-lg font-semibold text-foreground">No exchanges connected</h3>
              <p className="mt-2 text-sm text-muted-foreground">
                Connect your first exchange to enable automated trading.
              </p>
              <Button className="mt-4" onClick={() => setIsCreateOpen(true)}>
                <Plus className="mr-2 h-4 w-4" />
                Add Exchange
              </Button>
            </div>
          ) : (
            <div className="rounded-xl border border-border bg-card">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>Exchange</TableHead>
                    <TableHead>Mode</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Created</TableHead>
                    <TableHead className="w-[50px]"></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {exchanges.map((exchange) => (
                    <TableRow key={exchange.id}>
                      <TableCell className="font-medium">{exchange.name}</TableCell>
                      <TableCell className="capitalize">{exchange.exchange}</TableCell>
                      <TableCell>
                        <Badge variant={exchange.testnet ? "secondary" : "default"}>
                          {exchange.testnet ? "Testnet" : "Live"}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <div
                            className={cn(
                              "h-2 w-2 rounded-full",
                              exchange.status === "connected" && "bg-success",
                              exchange.status === "disconnected" && "bg-muted-foreground",
                              exchange.status === "error" && "bg-destructive",
                            )}
                          />
                          <span className="capitalize">{exchange.status}</span>
                        </div>
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {new Date(exchange.createdAt).toLocaleDateString()}
                      </TableCell>
                      <TableCell>
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button variant="ghost" size="icon" className="h-8 w-8">
                              <MoreVertical className="h-4 w-4" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem onClick={() => handleReconnect(exchange.id)}>
                              <RefreshCw className="mr-2 h-4 w-4" />
                              Reconnect
                            </DropdownMenuItem>
                            <DropdownMenuItem className="text-destructive" onClick={() => handleDelete(exchange.id)}>
                              <Trash2 className="mr-2 h-4 w-4" />
                              Delete
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </div>

        <CreateExchangeModal open={isCreateOpen} onOpenChange={setIsCreateOpen} onSuccess={() => mutate()} />
      </main>
    </div>
  )
}
