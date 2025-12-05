"use client"

import { useState, useEffect } from "react"
import { Sidebar } from "@/components/layout/sidebar"
import { Header } from "@/components/layout/header"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Switch } from "@/components/ui/switch"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Server, Wifi, WifiOff, RefreshCw, Check, X, Globe, Database, Bell } from "lucide-react"
import { checkHealth } from "@/lib/api"
import { useWebSocket } from "@/hooks/use-websocket"
import { cn } from "@/lib/utils"

export default function SettingsPage() {
  const [apiUrl, setApiUrl] = useState("http://localhost:8000")
  const [wsUrl, setWsUrl] = useState("ws://localhost:8000")
  const [apiStatus, setApiStatus] = useState<"checking" | "connected" | "error">("error")
  const [apiInfo, setApiInfo] = useState<{
    exchanges_connected: number
    models_registered: number
  } | null>(null)

  const { status: wsStatus, isConnected, connect } = useWebSocket(false)

  const [notifications, setNotifications] = useState({
    signals: true,
    orders: true,
    errors: true,
  })

  const checkApiConnection = async () => {
    setApiStatus("checking")
    const { data, error } = await checkHealth()
    if (error) {
      setApiStatus("error")
      setApiInfo(null)
    } else if (data) {
      setApiStatus("connected")
      setApiInfo({
        exchanges_connected: data.exchanges_connected,
        models_registered: data.models_registered,
      })
    }
  }

  useEffect(() => {
    // Set initial status without checking
    setApiStatus("error")
  }, [])

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="flex-1 pl-64">
        <Header title="Settings" description="Configure your trading system" />

        <div className="p-6">
          <Tabs defaultValue="connection">
            <TabsList>
              <TabsTrigger value="connection">Connection</TabsTrigger>
              <TabsTrigger value="notifications">Notifications</TabsTrigger>
              <TabsTrigger value="trading">Trading</TabsTrigger>
            </TabsList>

            <TabsContent value="connection" className="mt-6 space-y-6">
              {/* Demo Mode Notice */}
              <Card className="border-warning/50 bg-warning/5">
                <CardContent className="p-4">
                  <p className="text-sm text-warning">
                    <strong>Demo Mode:</strong> The app is running without a backend connection. To enable live trading,
                    run the Python backend server and configure the connection below.
                  </p>
                </CardContent>
              </Card>

              {/* Backend API Connection */}
              <Card>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
                        <Server className="h-5 w-5 text-primary" />
                      </div>
                      <div>
                        <CardTitle>Backend API</CardTitle>
                        <CardDescription>Python FastAPI server connection</CardDescription>
                      </div>
                    </div>
                    <Badge
                      variant={apiStatus === "connected" ? "default" : "secondary"}
                      className={cn(apiStatus === "connected" && "bg-success text-success-foreground")}
                    >
                      {apiStatus === "checking" ? (
                        <RefreshCw className="mr-1 h-3 w-3 animate-spin" />
                      ) : apiStatus === "connected" ? (
                        <Check className="mr-1 h-3 w-3" />
                      ) : (
                        <X className="mr-1 h-3 w-3" />
                      )}
                      {apiStatus === "checking"
                        ? "Checking..."
                        : apiStatus === "connected"
                          ? "Connected"
                          : "Not Connected"}
                    </Badge>
                  </div>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="apiUrl">API URL</Label>
                    <div className="flex gap-2">
                      <Input
                        id="apiUrl"
                        value={apiUrl}
                        onChange={(e) => setApiUrl(e.target.value)}
                        placeholder="http://localhost:8000"
                      />
                      <Button variant="outline" onClick={checkApiConnection}>
                        <RefreshCw className={cn("h-4 w-4", apiStatus === "checking" && "animate-spin")} />
                      </Button>
                    </div>
                  </div>

                  {apiInfo && (
                    <div className="grid gap-4 md:grid-cols-2">
                      <div className="rounded-lg border border-border p-3">
                        <p className="text-sm text-muted-foreground">Exchanges Connected</p>
                        <p className="text-2xl font-bold text-foreground">{apiInfo.exchanges_connected}</p>
                      </div>
                      <div className="rounded-lg border border-border p-3">
                        <p className="text-sm text-muted-foreground">Models Registered</p>
                        <p className="text-2xl font-bold text-foreground">{apiInfo.models_registered}</p>
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* WebSocket Connection */}
              <Card>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
                        {isConnected ? (
                          <Wifi className="h-5 w-5 text-primary" />
                        ) : (
                          <WifiOff className="h-5 w-5 text-muted-foreground" />
                        )}
                      </div>
                      <div>
                        <CardTitle>WebSocket</CardTitle>
                        <CardDescription>Real-time data streaming</CardDescription>
                      </div>
                    </div>
                    <Badge
                      variant={isConnected ? "default" : "secondary"}
                      className={cn(isConnected && "bg-success text-success-foreground")}
                    >
                      {isConnected ? "Connected" : "Not Connected"}
                    </Badge>
                  </div>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="wsUrl">WebSocket URL</Label>
                    <div className="flex gap-2">
                      <Input
                        id="wsUrl"
                        value={wsUrl}
                        onChange={(e) => setWsUrl(e.target.value)}
                        placeholder="ws://localhost:8000"
                      />
                      <Button variant="outline" onClick={connect}>
                        Connect
                      </Button>
                    </div>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Click Connect to establish a WebSocket connection to the backend server.
                  </p>
                </CardContent>
              </Card>

              {/* Environment Info */}
              <Card>
                <CardHeader>
                  <div className="flex items-center gap-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
                      <Globe className="h-5 w-5 text-primary" />
                    </div>
                    <div>
                      <CardTitle>Environment</CardTitle>
                      <CardDescription>Current environment configuration</CardDescription>
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    <div className="flex items-center justify-between rounded-lg border border-border p-3">
                      <span className="text-sm text-muted-foreground">NEXT_PUBLIC_API_URL</span>
                      <code className="text-xs text-foreground">{process.env.NEXT_PUBLIC_API_URL || "Not set"}</code>
                    </div>
                    <div className="flex items-center justify-between rounded-lg border border-border p-3">
                      <span className="text-sm text-muted-foreground">NEXT_PUBLIC_WS_URL</span>
                      <code className="text-xs text-foreground">{process.env.NEXT_PUBLIC_WS_URL || "Not set"}</code>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="notifications" className="mt-6">
              <Card>
                <CardHeader>
                  <div className="flex items-center gap-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
                      <Bell className="h-5 w-5 text-primary" />
                    </div>
                    <div>
                      <CardTitle>Notification Settings</CardTitle>
                      <CardDescription>Configure alert preferences</CardDescription>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="space-y-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-medium text-foreground">Trading Signals</p>
                      <p className="text-sm text-muted-foreground">Get notified when AI generates buy/sell signals</p>
                    </div>
                    <Switch
                      checked={notifications.signals}
                      onCheckedChange={(checked) => setNotifications({ ...notifications, signals: checked })}
                    />
                  </div>
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-medium text-foreground">Order Execution</p>
                      <p className="text-sm text-muted-foreground">Notify when orders are filled or canceled</p>
                    </div>
                    <Switch
                      checked={notifications.orders}
                      onCheckedChange={(checked) => setNotifications({ ...notifications, orders: checked })}
                    />
                  </div>
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-medium text-foreground">Error Alerts</p>
                      <p className="text-sm text-muted-foreground">Get notified about connection or trading errors</p>
                    </div>
                    <Switch
                      checked={notifications.errors}
                      onCheckedChange={(checked) => setNotifications({ ...notifications, errors: checked })}
                    />
                  </div>
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="trading" className="mt-6">
              <Card>
                <CardHeader>
                  <div className="flex items-center gap-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
                      <Database className="h-5 w-5 text-primary" />
                    </div>
                    <div>
                      <CardTitle>Trading Settings</CardTitle>
                      <CardDescription>Default trading parameters</CardDescription>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid gap-4 md:grid-cols-2">
                    <div className="space-y-2">
                      <Label htmlFor="defaultAmount">Default Order Amount (USDT)</Label>
                      <Input id="defaultAmount" type="number" placeholder="100" defaultValue="100" />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="maxOrders">Max Open Orders per Agent</Label>
                      <Input id="maxOrders" type="number" placeholder="5" defaultValue="5" />
                    </div>
                  </div>
                  <div className="grid gap-4 md:grid-cols-2">
                    <div className="space-y-2">
                      <Label htmlFor="defaultTp">Default Take Profit (%)</Label>
                      <Input id="defaultTp" type="number" placeholder="5" defaultValue="5" />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="defaultSl">Default Stop Loss (%)</Label>
                      <Input id="defaultSl" type="number" placeholder="2" defaultValue="2" />
                    </div>
                  </div>
                  <Button>Save Trading Settings</Button>
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </div>
      </main>
    </div>
  )
}
