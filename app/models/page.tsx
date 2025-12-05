"use client"

import { useState } from "react"
import { useAppStore } from "@/lib/store"
import { Sidebar } from "@/components/layout/sidebar"
import { Header } from "@/components/layout/header"
import { CreateModelModal } from "@/components/modals/create-model-modal"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { Plus, MoreVertical, Brain, Trash2, Edit } from "lucide-react"

export default function ModelsPage() {
  const { models, deleteModel, updateModel } = useAppStore()
  const [isCreateOpen, setIsCreateOpen] = useState(false)

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="flex-1 pl-64">
        <Header title="AI Models" description="Manage your AI model configurations" />

        <div className="p-6">
          <div className="mb-6 flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">
                {models.length} model{models.length !== 1 ? "s" : ""} configured
              </p>
            </div>
            <Button onClick={() => setIsCreateOpen(true)}>
              <Plus className="mr-2 h-4 w-4" />
              Add Model
            </Button>
          </div>

          {models.length === 0 ? (
            <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-border bg-card p-12 text-center">
              <Brain className="h-12 w-12 text-muted-foreground" />
              <h3 className="mt-4 text-lg font-semibold text-foreground">No models configured</h3>
              <p className="mt-2 text-sm text-muted-foreground">
                Add your first AI model to start creating trading agents.
              </p>
              <Button className="mt-4" onClick={() => setIsCreateOpen(true)}>
                <Plus className="mr-2 h-4 w-4" />
                Add Model
              </Button>
            </div>
          ) : (
            <div className="rounded-xl border border-border bg-card">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>Provider</TableHead>
                    <TableHead>Model</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Created</TableHead>
                    <TableHead className="w-[50px]"></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {models.map((model) => (
                    <TableRow key={model.id}>
                      <TableCell className="font-medium">{model.name}</TableCell>
                      <TableCell className="capitalize">{model.provider}</TableCell>
                      <TableCell>
                        <code className="rounded bg-secondary px-2 py-1 text-xs">{model.model}</code>
                      </TableCell>
                      <TableCell>
                        <Badge variant={model.status === "active" ? "default" : "secondary"}>{model.status}</Badge>
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {new Date(model.createdAt).toLocaleDateString()}
                      </TableCell>
                      <TableCell>
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button variant="ghost" size="icon" className="h-8 w-8">
                              <MoreVertical className="h-4 w-4" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem
                              onClick={() =>
                                updateModel(model.id, {
                                  status: model.status === "active" ? "inactive" : "active",
                                })
                              }
                            >
                              <Edit className="mr-2 h-4 w-4" />
                              {model.status === "active" ? "Deactivate" : "Activate"}
                            </DropdownMenuItem>
                            <DropdownMenuItem className="text-destructive" onClick={() => deleteModel(model.id)}>
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

        <CreateModelModal open={isCreateOpen} onOpenChange={setIsCreateOpen} />
      </main>
    </div>
  )
}
