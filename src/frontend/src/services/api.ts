import axios, { AxiosInstance, AxiosError } from 'axios'
import type {
  User,
  Workflow,
  Lead,
  CreateUserRequest,
  CreateWorkflowRequest,
  CreateLeadRequest,
  LoginRequest,
  LoginResponse,
  WorkflowSettings,
  UpdateWorkflowSettingsRequest,
  Funnel,
  Status,
  Field,
  FieldMapping,
  CreateFieldMappingRequest,
  UpdateFieldMappingRequest,
} from '@/types'

const api: AxiosInstance = axios.create({
  baseURL: '/api/v1',
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    // Не делаем автоматический редирект для /auth/me, так как ProtectedRoute сам обрабатывает это
    // Редирект только для других запросов, когда пользователь уже был авторизован
    if (error.response?.status === 401) {
      const url = error.config?.url || ''
      // Пропускаем редирект для запросов проверки авторизации
      if (!url.includes('/auth/me')) {
        // Проверяем, что мы не на странице логина
        if (window.location.pathname !== '/login') {
          window.location.href = '/login'
        }
      }
    }
    return Promise.reject(error)
  }
)

// Auth API
export const authAPI = {
  login: async (data: LoginRequest): Promise<LoginResponse> => {
    const response = await api.post<LoginResponse>('/auth/login', data)
    return response.data
  },

  logout: async (): Promise<void> => {
    await api.post('/auth/logout')
  },

  getCurrentUser: async (): Promise<User> => {
    const response = await api.get<User>('/auth/me')
    return response.data
  },
}

// Users API (admin only)
export const usersAPI = {
  list: async (): Promise<User[]> => {
    const response = await api.get<User[]>('/users')
    return response.data
  },

  create: async (data: CreateUserRequest): Promise<User> => {
    const response = await api.post<User>('/users', data)
    return response.data
  },
}

// Workflows API
export const workflowsAPI = {
  list: async (): Promise<Workflow[]> => {
    const response = await api.get<Workflow[]>('/workflows')
    return response.data
  },

  get: async (id: number): Promise<Workflow> => {
    const response = await api.get<Workflow>(`/workflows/${id}`)
    return response.data
  },

  create: async (data: CreateWorkflowRequest): Promise<Workflow> => {
    const response = await api.post<Workflow>('/workflows', data)
    return response.data
  },

  delete: async (id: number): Promise<void> => {
    await api.delete(`/workflows/${id}`)
  },

  getSettings: async (workflowId: number): Promise<WorkflowSettings> => {
    const response = await api.get<WorkflowSettings>(`/workflows/${workflowId}/settings`)
    return response.data
  },

  updateSettings: async (
    workflowId: number,
    settings: UpdateWorkflowSettingsRequest
  ): Promise<WorkflowSettings> => {
    const response = await api.put<WorkflowSettings>(`/workflows/${workflowId}/settings`, settings)
    return response.data
  },

  getFunnels: async (workflowId: number): Promise<Funnel[]> => {
    const response = await api.get<Funnel[]>(`/workflows/${workflowId}/settings/funnels`)
    return response.data
  },

  getStages: async (workflowId: number, categoryId: number = 0): Promise<Status[]> => {
    const response = await api.get<Status[]>(
      `/workflows/${workflowId}/settings/stages?category_id=${categoryId}`
    )
    return response.data
  },

  getLeadStatuses: async (workflowId: number): Promise<Status[]> => {
    const response = await api.get<Status[]>(`/workflows/${workflowId}/settings/lead-statuses`)
    return response.data
  },

  getFields: async (workflowId: number, entityType: 'lead' | 'deal' = 'lead'): Promise<Field[]> => {
    const response = await api.get<Field[]>(`/workflows/${workflowId}/fields?entity_type=${entityType}`)
    return response.data
  },

  getFieldMappings: async (workflowId: number): Promise<FieldMapping[]> => {
    const response = await api.get<FieldMapping[]>(`/workflows/${workflowId}/fields/mapping`)
    return response.data
  },

  createFieldMapping: async (
    workflowId: number,
    data: CreateFieldMappingRequest
  ): Promise<FieldMapping> => {
    const response = await api.post<FieldMapping>(`/workflows/${workflowId}/fields/mapping`, data)
    return response.data
  },

  updateFieldMapping: async (
    workflowId: number,
    mappingId: number,
    data: UpdateFieldMappingRequest
  ): Promise<FieldMapping> => {
    const response = await api.put<FieldMapping>(
      `/workflows/${workflowId}/fields/mapping/${mappingId}`,
      data
    )
    return response.data
  },

  deleteFieldMapping: async (workflowId: number, mappingId: number): Promise<void> => {
    await api.delete(`/workflows/${workflowId}/fields/mapping/${mappingId}`)
  },

  generateApiToken: async (workflowId: number): Promise<{ api_token: string }> => {
    const response = await api.post<{ api_token: string }>(`/workflows/${workflowId}/settings/generate-token`)
    return response.data
  },

  getConversionStats: async (workflowId: number): Promise<{ total: number; successful: number; percentage: number }> => {
    const response = await api.get<{ total: number; successful: number; percentage: number }>(`/workflows/${workflowId}/stats/conversion`)
    return response.data
  },
}

// Leads API
export const leadsAPI = {
  list: async (workflowId: number): Promise<Lead[]> => {
    const response = await api.get<Lead[]>(`/workflows/${workflowId}/leads`)
    return response.data
  },

  create: async (workflowId: number, data: CreateLeadRequest): Promise<Lead> => {
    const response = await api.post<Lead>(`/workflows/${workflowId}/leads`, data)
    return response.data
  },

  uploadCSV: async (
    workflowId: number,
    file: File,
    columnMapping?: Record<string, string>,
    limit?: number | null,
    onProgress?: (progress: { loaded: number; total: number }) => void
  ): Promise<Lead[]> => {
    const formData = new FormData()
    formData.append('file', file)
    if (columnMapping) {
      formData.append('column_mapping', JSON.stringify(columnMapping))
    }
    if (limit !== undefined && limit !== null) {
      formData.append('limit', limit.toString())
    }
    const response = await api.post<Lead[]>(`/workflows/${workflowId}/leads/upload`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      onUploadProgress: (progressEvent) => {
        if (progressEvent.total && onProgress) {
          onProgress({
            loaded: progressEvent.loaded,
            total: progressEvent.total,
          })
        }
      },
    })
    return response.data
  },
}

export default api

