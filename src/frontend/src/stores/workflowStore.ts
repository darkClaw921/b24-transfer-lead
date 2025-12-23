import { create } from 'zustand'
import type { Workflow } from '@/types'
import { workflowsAPI } from '@/services/api'

interface WorkflowState {
  workflows: Workflow[]
  loading: boolean
  fetchWorkflows: () => Promise<void>
  createWorkflow: (data: { name: string; bitrix24_webhook_url: string }) => Promise<void>
  deleteWorkflow: (id: number) => Promise<void>
}

export const useWorkflowStore = create<WorkflowState>((set) => ({
  workflows: [],
  loading: false,

  fetchWorkflows: async () => {
    set({ loading: true })
    try {
      const workflows = await workflowsAPI.list()
      set({ workflows, loading: false })
    } catch (error) {
      set({ loading: false })
      throw error
    }
  },

  createWorkflow: async (data) => {
    try {
      const workflow = await workflowsAPI.create(data)
      set((state) => ({
        workflows: [...state.workflows, workflow],
      }))
    } catch (error) {
      throw error
    }
  },

  deleteWorkflow: async (id: number) => {
    try {
      await workflowsAPI.delete(id)
      set((state) => ({
        workflows: state.workflows.filter((w) => w.id !== id),
      }))
    } catch (error) {
      throw error
    }
  },
}))

