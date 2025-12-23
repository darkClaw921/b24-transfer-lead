import { create } from 'zustand'
import type { Lead } from '@/types'
import { leadsAPI } from '@/services/api'

interface LeadsState {
  leads: Lead[]
  loading: boolean
  currentWorkflowId: number | null
  fetchLeads: (workflowId: number) => Promise<void>
  createLead: (workflowId: number, phone: string, name: string, additionalFields?: Record<string, string>) => Promise<void>
  uploadCSV: (workflowId: number, file: File, columnMapping?: Record<string, string>, limit?: number | null, onProgress?: (progress: { loaded: number; total: number }) => void) => Promise<void>
}

export const useLeadsStore = create<LeadsState>((set, get) => ({
  leads: [],
  loading: false,
  currentWorkflowId: null,

  fetchLeads: async (workflowId: number) => {
    // Prevent duplicate requests for the same workflow
    const state = get()
    if (state.loading && state.currentWorkflowId === workflowId) {
      return
    }

    set({ loading: true, currentWorkflowId: workflowId })
    try {
      const leads = await leadsAPI.list(workflowId)
      set({ leads, loading: false })
    } catch (error) {
      set({ loading: false })
      throw error
    }
  },

  createLead: async (workflowId: number, phone: string, name: string, additionalFields?: Record<string, string>) => {
    try {
      const leadData = { phone, name, ...additionalFields } as { phone: string; name: string; [key: string]: string | undefined }
      const lead = await leadsAPI.create(workflowId, leadData)
      set((state) => ({
        leads: [...state.leads, lead],
      }))
    } catch (error) {
      throw error
    }
  },

  uploadCSV: async (workflowId: number, file: File, columnMapping?: Record<string, string>, limit?: number | null, onProgress?: (progress: { loaded: number; total: number }) => void) => {
    set({ loading: true })
    try {
      const leads = await leadsAPI.uploadCSV(workflowId, file, columnMapping, limit, onProgress)
      set((state) => ({
        leads: [...state.leads, ...leads],
        loading: false,
      }))
    } catch (error) {
      set({ loading: false })
      throw error
    }
  },
}))

