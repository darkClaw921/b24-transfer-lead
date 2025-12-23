export interface User {
  id: number
  username: string
  role: 'admin' | 'user'
  created_at?: string
}

export interface Workflow {
  id: number
  name: string
  bitrix24_webhook_url: string
  user_id: number
  created_at: string
}

export interface LeadField {
  field_name: string
  field_value: string
}

export interface Lead {
  id: number
  phone: string
  name: string
  status: string | null
  bitrix24_lead_id: string | null
  assigned_by_name: string | null  // Имя и фамилия ответственного
  status_semantic_id: string | null  // Семантический ID статуса (S/F) для определения цвета
  created_at: string
  updated_at: string
  fields?: LeadField[]
}

export interface CreateUserRequest {
  username: string
  password: string
  role?: string
  workflow_ids?: number[]  // List of workflow IDs user should have access to
}

export interface CreateWorkflowRequest {
  name: string
  bitrix24_webhook_url: string  // Full URL: https://domain.bitrix24.ru/rest/1/token
}

export interface CreateLeadRequest {
  phone: string
  name: string
  [key: string]: string | undefined  // Additional fields
}

export interface LoginRequest {
  username: string
  password: string
}

export interface LoginResponse {
  username: string
  role: string
  message: string
}

export type EntityType = 'lead' | 'deal'

export interface WorkflowSettings {
  entity_type: EntityType
  deal_category_id: number | null
  deal_stage_id: string | null
  lead_status_id: string | null
  bitrix24_webhook_url: string
  app_token: string | null
  webhook_endpoint_url: string  // Full URL for Bitrix24 to send events to
  api_token: string | null  // API token for public endpoint
  public_api_url: string | null  // Full URL for public API endpoint
}

export interface UpdateWorkflowSettingsRequest {
  entity_type: EntityType
  deal_category_id?: number | null
  deal_stage_id?: string | null
  lead_status_id?: string | null
  bitrix24_webhook_url?: string | null
  app_token?: string | null
}

export interface Funnel {
  id: number
  name: string
}

export interface Status {
  id: string
  name: string
}

export interface Field {
  id: string
  name: string
  type: string
}

export interface FieldMapping {
  id: number
  workflow_id: number
  field_name: string
  display_name: string
  bitrix24_field_id: string
  bitrix24_field_name: string
  entity_type: EntityType
  update_on_event: boolean
  created_at: string
}

export interface CreateFieldMappingRequest {
  field_name: string
  display_name: string
  bitrix24_field_id: string
  entity_type: EntityType
  update_on_event?: boolean
}

export interface UpdateFieldMappingRequest {
  field_name?: string
  display_name?: string
  bitrix24_field_id?: string
  entity_type?: EntityType
  update_on_event?: boolean
}

