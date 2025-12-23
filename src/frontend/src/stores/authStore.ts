import { create } from 'zustand'
import type { User } from '@/types'
import { authAPI } from '@/services/api'

interface AuthState {
  user: User | null
  loading: boolean
  checkingAuth: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => Promise<void>
  checkAuth: () => Promise<void>
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  loading: false,
  checkingAuth: false,

  login: async (username: string, password: string) => {
    set({ loading: true })
    try {
      await authAPI.login({ username, password })
      const user = await authAPI.getCurrentUser()
      set({ user, loading: false })
    } catch (error) {
      set({ loading: false })
      throw error
    }
  },

  logout: async () => {
    try {
      await authAPI.logout()
    } finally {
      set({ user: null })
    }
  },

  checkAuth: async () => {
    // Prevent multiple simultaneous auth checks
    if (get().checkingAuth) {
      return
    }
    
    set({ checkingAuth: true, loading: true })
    try {
      const user = await authAPI.getCurrentUser()
      set({ user, loading: false, checkingAuth: false })
    } catch (error) {
      set({ user: null, loading: false, checkingAuth: false })
    }
  },
}))

