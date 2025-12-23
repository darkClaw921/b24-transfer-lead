import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { workflowsAPI } from '@/services/api'
import { useAuthStore } from '@/stores/authStore'
import type {
  WorkflowSettings,
  UpdateWorkflowSettingsRequest,
  Funnel,
  Status,
  Field,
  FieldMapping,
  CreateFieldMappingRequest,
  UpdateFieldMappingRequest,
} from '@/types'
import { ArrowLeft, Save, Loader2, Copy, Check, Settings2, Plus, Trash2, X } from 'lucide-react'

export default function WorkflowSettingsPage() {
  const { id } = useParams<{ id: string }>()
  const workflowId = parseInt(id || '0', 10)
  const navigate = useNavigate()

  const [settings, setSettings] = useState<WorkflowSettings>({
    entity_type: 'lead',
    deal_category_id: null,
    deal_stage_id: null,
    lead_status_id: null,
    bitrix24_webhook_url: '',
    app_token: null,
    webhook_endpoint_url: '',
    api_token: null,
    public_api_url: null,
  })
  const [generatingToken, setGeneratingToken] = useState(false)
  const [funnels, setFunnels] = useState<Funnel[]>([])
  const [stages, setStages] = useState<Status[]>([])
  const [leadStatuses, setLeadStatuses] = useState<Status[]>([])

  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [loadingFunnels, setLoadingFunnels] = useState(false)
  const [loadingStages, setLoadingStages] = useState(false)
  const [loadingLeadStatuses, setLoadingLeadStatuses] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)
  
  // Field mapping state
  const [showFieldMappingModal, setShowFieldMappingModal] = useState(false)
  const [fields, setFields] = useState<Field[]>([])
  const [fieldMappings, setFieldMappings] = useState<FieldMapping[]>([])
  const [loadingFields, setLoadingFields] = useState(false)
  const [loadingMappings, setLoadingMappings] = useState(false)
  const [newMapping, setNewMapping] = useState<CreateFieldMappingRequest>({
    field_name: '',
    display_name: '',
    bitrix24_field_id: '',
    entity_type: 'lead',
    update_on_event: false,
  })
  const [editingMapping, setEditingMapping] = useState<FieldMapping | null>(null)
  const [editMappingData, setEditMappingData] = useState<UpdateFieldMappingRequest>({})
  
  const { user } = useAuthStore()
  const isAdmin = user?.role === 'admin'

  useEffect(() => {
    loadSettings()
    // Загружаем маппинги для всех пользователей, чтобы показывать примеры API
    loadFieldMappings()
  }, [workflowId])

  useEffect(() => {
    if (settings.entity_type === 'deal') {
      loadFunnels()
      if (settings.deal_category_id !== null) {
        loadStages(settings.deal_category_id)
      }
    } else {
      loadLeadStatuses()
    }
  }, [settings.entity_type, settings.deal_category_id])

  const loadSettings = async () => {
    try {
      setLoading(true)
      setError(null)
      const data = await workflowsAPI.getSettings(workflowId)
      setSettings(data)
    } catch (err) {
      setError('Ошибка при загрузке настроек')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const loadFunnels = async () => {
    try {
      setLoadingFunnels(true)
      setError(null)
      const data = await workflowsAPI.getFunnels(workflowId)
      console.log('Loaded funnels:', data)
      setFunnels(data)
      if (data.length === 0) {
        setError('Воронки не найдены. Проверьте настройки Bitrix24.')
      }
    } catch (err) {
      setError('Ошибка при загрузке воронок')
      console.error('Error loading funnels:', err)
    } finally {
      setLoadingFunnels(false)
    }
  }

  const loadStages = async (categoryId: number) => {
    try {
      setLoadingStages(true)
      const data = await workflowsAPI.getStages(workflowId, categoryId)
      setStages(data)
      // Сбросить выбранную стадию, если она не существует в новой воронке
      if (data.length > 0 && !data.find((s) => s.id === settings.deal_stage_id)) {
        setSettings((prev) => ({ ...prev, deal_stage_id: data[0].id }))
      }
    } catch (err) {
      setError('Ошибка при загрузке стадий')
      console.error(err)
    } finally {
      setLoadingStages(false)
    }
  }

  const loadLeadStatuses = async () => {
    try {
      setLoadingLeadStatuses(true)
      const data = await workflowsAPI.getLeadStatuses(workflowId)
      setLeadStatuses(data)
    } catch (err) {
      setError('Ошибка при загрузке статусов лидов')
      console.error(err)
    } finally {
      setLoadingLeadStatuses(false)
    }
  }

  const handleEntityTypeChange = (entityType: 'lead' | 'deal') => {
    setSettings((prev) => ({
      ...prev,
      entity_type: entityType,
      deal_category_id: entityType === 'deal' ? prev.deal_category_id : null,
      deal_stage_id: entityType === 'deal' ? prev.deal_stage_id : null,
      lead_status_id: entityType === 'lead' ? prev.lead_status_id : null,
    }))
  }

  const handleFunnelChange = (categoryId: number) => {
    setSettings((prev) => ({
      ...prev,
      deal_category_id: categoryId,
      deal_stage_id: null, // Сбросить стадию при смене воронки
    }))
    loadStages(categoryId)
  }

  const loadFieldMappings = async () => {
    try {
      setLoadingMappings(true)
      const data = await workflowsAPI.getFieldMappings(workflowId)
      setFieldMappings(data)
    } catch (err) {
      console.error('Error loading field mappings:', err)
    } finally {
      setLoadingMappings(false)
    }
  }

  const loadFields = async (entityType: 'lead' | 'deal') => {
    try {
      setLoadingFields(true)
      const data = await workflowsAPI.getFields(workflowId, entityType)
      setFields(data)
    } catch (err) {
      setError('Ошибка при загрузке полей')
      console.error(err)
    } finally {
      setLoadingFields(false)
    }
  }

  const handleOpenFieldMappingModal = async () => {
    setShowFieldMappingModal(true)
    setEditingMapping(null)
    setNewMapping({
      field_name: '',
      display_name: '',
      bitrix24_field_id: '',
      entity_type: settings.entity_type,
      update_on_event: false,
    })
    await loadFields(settings.entity_type)
  }

  const handleEditFieldMapping = async (mapping: FieldMapping) => {
    setEditingMapping(mapping)
    setEditMappingData({
      field_name: mapping.field_name,
      display_name: mapping.display_name,
      bitrix24_field_id: mapping.bitrix24_field_id,
      entity_type: mapping.entity_type,
      update_on_event: mapping.update_on_event,
    })
    setShowFieldMappingModal(true)
    await loadFields(mapping.entity_type)
  }

  const handleCreateFieldMapping = async () => {
    if (!newMapping.field_name || !newMapping.display_name || !newMapping.bitrix24_field_id) {
      setError('Заполните все поля')
      return
    }
    try {
      await workflowsAPI.createFieldMapping(workflowId, newMapping)
      await loadFieldMappings()
      setShowFieldMappingModal(false)
      setNewMapping({ field_name: '', display_name: '', bitrix24_field_id: '', entity_type: 'lead', update_on_event: false })
      setError(null)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Ошибка при создании маппинга')
      console.error(err)
    }
  }

  const handleUpdateFieldMapping = async () => {
    if (!editingMapping) return
    if (!editMappingData.field_name || !editMappingData.display_name) {
      setError('Заполните все обязательные поля')
      return
    }
    try {
      await workflowsAPI.updateFieldMapping(workflowId, editingMapping.id, editMappingData)
      await loadFieldMappings()
      setShowFieldMappingModal(false)
      setEditingMapping(null)
      setEditMappingData({})
      setError(null)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Ошибка при обновлении маппинга')
      console.error(err)
    }
  }

  const handleDeleteFieldMapping = async (mappingId: number) => {
    if (!confirm('Вы уверены, что хотите удалить этот маппинг поля?')) {
      return
    }
    try {
      await workflowsAPI.deleteFieldMapping(workflowId, mappingId)
      await loadFieldMappings()
    } catch (err) {
      setError('Ошибка при удалении маппинга')
      console.error(err)
    }
  }

  const handleSave = async () => {
    try {
      setSaving(true)
      setError(null)
      const updateData: UpdateWorkflowSettingsRequest = {
        entity_type: settings.entity_type,
        deal_category_id: settings.deal_category_id,
        deal_stage_id: settings.deal_stage_id,
        lead_status_id: settings.lead_status_id,
        bitrix24_webhook_url: settings.bitrix24_webhook_url,
        app_token: settings.app_token,
      }
      await workflowsAPI.updateSettings(workflowId, updateData)
      navigate(`/workflows/${workflowId}/leads`)
    } catch (err) {
      setError('Ошибка при сохранении настроек')
      console.error(err)
    } finally {
      setSaving(false)
    }
  }

  const handleGenerateToken = async () => {
    if (!confirm('Вы уверены, что хотите сгенерировать новый токен? Старый токен перестанет работать.')) {
      return
    }
    try {
      setGeneratingToken(true)
      setError(null)
      await workflowsAPI.generateApiToken(workflowId)
      // Reload settings to get updated public_api_url
      await loadSettings()
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Ошибка при генерации токена')
      console.error(err)
    } finally {
      setGeneratingToken(false)
    }
  }

  const generateExampleData = () => {
    // Фильтруем маппинги по текущему типу сущности
    const relevantMappings = fieldMappings.filter(
      (m) => m.entity_type === settings.entity_type
    )
    
    // Базовые обязательные поля
    const exampleData: Record<string, string> = {
      name: 'Иван Иванов',
      phone: '+79991234567',
    }
    
    // Добавляем примеры значений для всех полей из маппинга
    relevantMappings.forEach((mapping) => {
      // Пропускаем name и phone, так как они уже есть
      if (mapping.field_name === 'name' || mapping.field_name === 'phone') {
        return
      }
      
      // Генерируем пример значения в зависимости от типа поля
      let exampleValue = ''
      const fieldName = mapping.field_name.toLowerCase()
      
      if (fieldName.includes('email')) {
        exampleValue = 'ivan@example.com'
      } else if (fieldName.includes('company') || fieldName.includes('компания')) {
        exampleValue = 'ООО "Пример"'
      } else if (fieldName.includes('comment') || fieldName.includes('комментарий') || fieldName.includes('message')) {
        exampleValue = 'Комментарий к лиду'
      } else if (fieldName.includes('source') || fieldName.includes('источник')) {
        exampleValue = 'Сайт'
      } else if (fieldName.includes('address') || fieldName.includes('адрес')) {
        exampleValue = 'г. Москва, ул. Примерная, д. 1'
      } else if (fieldName.includes('position') || fieldName.includes('должность')) {
        exampleValue = 'Менеджер'
      } else {
        exampleValue = `Пример ${mapping.display_name}`
      }
      
      exampleData[mapping.field_name] = exampleValue
    })
    
    return exampleData
  }

  const generateExampleJson = () => {
    const exampleData = generateExampleData()
    return JSON.stringify(exampleData, null, 2)
  }

  const generateExampleQueryParams = () => {
    const exampleData = generateExampleData()
    // Для примера показываем русские символы без кодирования для читаемости
    // В реальном использовании браузер автоматически закодирует URL при отправке запроса
    const params = Object.entries(exampleData)
      .map(([key, value]) => {
        // Заменяем пробелы на + для читаемости в URL, но оставляем русские символы как есть
        const urlValue = value.replace(/\s+/g, '+')
        return `${key}=${urlValue}`
      })
      .join('&')
    return params
  }

  if (loading) {
    return (
      <div className="px-4 py-6 sm:px-0">
        <div className="text-center py-8">Загрузка...</div>
      </div>
    )
  }

  return (
    <div className="px-4 py-6 sm:px-0">
      <div className="mb-6">
        <button
          onClick={() => navigate(`/workflows/${workflowId}/leads`)}
          className="inline-flex items-center text-sm text-gray-600 hover:text-gray-900 mb-4"
        >
          <ArrowLeft className="w-4 h-4 mr-1" />
          Назад к лидам
        </button>
        <h1 className="text-3xl font-bold text-gray-900">Настройки Workflow</h1>
      </div>

      {error && (
        <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-md text-red-800">
          {error}
        </div>
      )}

      <div className="bg-white rounded-lg shadow p-6 max-w-2xl">
        <div className="mb-6">
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Webhook URL Bitrix24
          </label>
          <input
            type="text"
            value={settings.bitrix24_webhook_url}
            onChange={(e) =>
              setSettings((prev) => ({ ...prev, bitrix24_webhook_url: e.target.value }))
            }
            placeholder="https://domain.bitrix24.ru/rest/1/token/"
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-blue-500 focus:border-blue-500"
          />
          <p className="mt-1 text-sm text-gray-500">
            Полный URL webhook для доступа к Bitrix24 API
          </p>
        </div>

        <div className="mb-6">
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Токен приложения
          </label>
          <input
            type="password"
            value={settings.app_token || ''}
            onChange={(e) =>
              setSettings((prev) => ({ ...prev, app_token: e.target.value || null }))
            }
            placeholder="e84pl0byhsxxaftwpa6qjhgcxlnfv0fj"
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-blue-500 focus:border-blue-500"
          />
          <p className="mt-1 text-sm text-gray-500">
            Токен приложения для проверки подлинности webhook событий от Bitrix24
          </p>
        </div>

        <div className="mb-6">
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Endpoint для событий Bitrix24
          </label>
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={settings.webhook_endpoint_url}
              readOnly
              className="flex-1 px-3 py-2 border border-gray-300 rounded-md bg-gray-50 text-gray-700 focus:outline-none focus:ring-blue-500 focus:border-blue-500"
            />
            <button
              type="button"
              onClick={() => {
                navigator.clipboard.writeText(settings.webhook_endpoint_url)
                setCopied(true)
                setTimeout(() => setCopied(false), 2000)
              }}
              className="px-3 py-2 border border-gray-300 rounded-md bg-white hover:bg-gray-50 text-gray-700 transition-colors"
              title="Копировать URL"
            >
              {copied ? (
                <Check className="w-4 h-4 text-green-600" />
              ) : (
                <Copy className="w-4 h-4" />
              )}
            </button>
          </div>
          <p className="mt-1 text-sm text-gray-500">
            Укажите этот URL в настройках webhook в Bitrix24 для отправки событий
          </p>
        </div>

        <div className="mb-6">
          <label className="block text-sm font-medium text-gray-700 mb-3">
            Тип сущности в Bitrix24
          </label>
          <div className="flex space-x-6">
            <label className="flex items-center">
              <input
                type="radio"
                name="entity_type"
                value="lead"
                checked={settings.entity_type === 'lead'}
                onChange={() => handleEntityTypeChange('lead')}
                className="mr-2"
              />
              <span>Лид</span>
            </label>
            <label className="flex items-center">
              <input
                type="radio"
                name="entity_type"
                value="deal"
                checked={settings.entity_type === 'deal'}
                onChange={() => handleEntityTypeChange('deal')}
                className="mr-2"
              />
              <span>Сделка</span>
            </label>
          </div>
        </div>

        {settings.entity_type === 'deal' && (
          <>
            <div className="mb-6">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Воронка сделок
              </label>
              {loadingFunnels ? (
                <div className="flex items-center text-gray-500">
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Загрузка воронок...
                </div>
              ) : funnels.length === 0 ? (
                <div className="text-sm text-gray-500">
                  Воронки не найдены. Проверьте настройки Bitrix24.
                </div>
              ) : (
                <select
                  value={settings.deal_category_id ?? ''}
                  onChange={(e) => handleFunnelChange(parseInt(e.target.value, 10))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                >
                  <option value="">Выберите воронку</option>
                  {funnels.map((funnel) => (
                    <option key={funnel.id} value={funnel.id}>
                      {funnel.name}
                    </option>
                  ))}
                </select>
              )}
            </div>

            {settings.deal_category_id !== null && (
              <div className="mb-6">
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Стадия сделки
                </label>
                {loadingStages ? (
                  <div className="flex items-center text-gray-500">
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    Загрузка стадий...
                  </div>
                ) : (
                  <select
                    value={settings.deal_stage_id ?? ''}
                    onChange={(e) =>
                      setSettings((prev) => ({ ...prev, deal_stage_id: e.target.value }))
                    }
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                  >
                    <option value="">Выберите стадию</option>
                    {stages.map((stage) => (
                      <option key={stage.id} value={stage.id}>
                        {stage.name}
                      </option>
                    ))}
                  </select>
                )}
              </div>
            )}
          </>
        )}

        {settings.entity_type === 'lead' && (
          <div className="mb-6">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Статус лида
            </label>
            {loadingLeadStatuses ? (
              <div className="flex items-center text-gray-500">
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Загрузка статусов...
              </div>
            ) : (
              <select
                value={settings.lead_status_id ?? ''}
                onChange={(e) =>
                  setSettings((prev) => ({ ...prev, lead_status_id: e.target.value }))
                }
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-blue-500 focus:border-blue-500"
              >
                <option value="">Выберите статус</option>
                {leadStatuses.map((status) => (
                  <option key={status.id} value={status.id}>
                    {status.name}
                  </option>
                ))}
              </select>
            )}
          </div>
        )}

        {isAdmin && (
          <>
            <div className="mb-6 pt-6 border-t">
              <div className="flex justify-between items-center mb-4">
                <h3 className="text-lg font-medium text-gray-900">Публичный API для добавления лидов</h3>
                {!settings.api_token && (
                  <button
                    onClick={handleGenerateToken}
                    disabled={generatingToken}
                    className="inline-flex items-center px-3 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 text-sm disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {generatingToken ? (
                      <>
                        <Loader2 className="w-4 h-4 mr-1 animate-spin" />
                        Генерация...
                      </>
                    ) : (
                      <>
                        <Plus className="w-4 h-4 mr-1" />
                        Сгенерировать токен
                      </>
                    )}
                  </button>
                )}
              </div>
              {settings.api_token ? (
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      API Endpoint URL
                    </label>
                    <div className="flex items-center gap-2">
                      <input
                        type="text"
                        value={settings.public_api_url || ''}
                        readOnly
                        className="flex-1 px-3 py-2 border border-gray-300 rounded-md bg-gray-50 text-gray-700 focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                      />
                      <button
                        type="button"
                        onClick={() => {
                          if (settings.public_api_url) {
                            navigator.clipboard.writeText(settings.public_api_url)
                            setCopied(true)
                            setTimeout(() => setCopied(false), 2000)
                          }
                        }}
                        className="px-3 py-2 border border-gray-300 rounded-md bg-white hover:bg-gray-50 text-gray-700 transition-colors"
                        title="Копировать URL"
                      >
                        {copied ? (
                          <Check className="w-4 h-4 text-green-600" />
                        ) : (
                          <Copy className="w-4 h-4" />
                        )}
                      </button>
                    </div>
                    <p className="mt-1 text-sm text-gray-500">
                      Используйте этот URL для создания лидов через публичный API без авторизации
                    </p>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      API Token
                    </label>
                    <div className="flex items-center gap-2">
                      <input
                        type="text"
                        value={settings.api_token}
                        readOnly
                        className="flex-1 px-3 py-2 border border-gray-300 rounded-md bg-gray-50 text-gray-700 font-mono text-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                      />
                      <button
                        type="button"
                        onClick={() => {
                          if (settings.api_token) {
                            navigator.clipboard.writeText(settings.api_token)
                            setCopied(true)
                            setTimeout(() => setCopied(false), 2000)
                          }
                        }}
                        className="px-3 py-2 border border-gray-300 rounded-md bg-white hover:bg-gray-50 text-gray-700 transition-colors"
                        title="Копировать токен"
                      >
                        {copied ? (
                          <Check className="w-4 h-4 text-green-600" />
                        ) : (
                          <Copy className="w-4 h-4" />
                        )}
                      </button>
                      <button
                        onClick={handleGenerateToken}
                        disabled={generatingToken}
                        className="px-3 py-2 border border-gray-300 rounded-md bg-white hover:bg-gray-50 text-gray-700 transition-colors text-sm disabled:opacity-50 disabled:cursor-not-allowed"
                        title="Регенерировать токен"
                      >
                        {generatingToken ? (
                          <Loader2 className="w-4 h-4 animate-spin" />
                        ) : (
                          <Settings2 className="w-4 h-4" />
                        )}
                      </button>
                    </div>
                    <p className="mt-1 text-sm text-gray-500">
                      Токен используется в URL для доступа к публичному API
                    </p>
                  </div>
                  <div className="mt-4 p-4 bg-blue-50 border border-blue-200 rounded-md">
                    <p className="text-sm font-medium text-blue-900 mb-2">Пример использования:</p>
                    {fieldMappings.filter((m) => m.entity_type === settings.entity_type).length > 0 ? (
                      <div className="space-y-3 text-xs font-mono text-blue-800">
                        <div>
                          <span className="font-semibold">1. POST запрос с JSON body:</span>
                          <div className="mt-1 text-xs text-blue-700 mb-1 break-all overflow-wrap-anywhere">
                            <span className="font-semibold">POST</span> {settings.public_api_url}
                          </div>
                          <pre className="mt-1 bg-white p-2 rounded border border-blue-200 overflow-x-auto whitespace-pre-wrap break-words">
{generateExampleJson()}
                          </pre>
                        </div>
                        <div className="mt-2">
                          <span className="font-semibold">2. GET или POST запрос с query параметрами:</span>
                          <div className="mt-1 bg-white p-2 rounded border border-blue-200 overflow-x-auto break-all overflow-wrap-anywhere">
                            <span className="font-semibold">GET</span> {settings.public_api_url}?{generateExampleQueryParams()}
                          </div>
                          <p className="mt-1 text-xs text-blue-600 italic break-words">
                            Примечание: GET запросы поддерживаются для удобства тестирования, но POST рекомендуется для production использования.
                          </p>
                        </div>
                      </div>
                    ) : (
                      <div className="space-y-3 text-xs font-mono text-blue-800">
                        <div>
                          <span className="font-semibold">1. POST запрос с JSON body:</span>
                          <div className="mt-1 text-xs text-blue-700 mb-1 break-all overflow-wrap-anywhere">
                            <span className="font-semibold">POST</span> {settings.public_api_url}
                          </div>
                          <pre className="mt-1 bg-white p-2 rounded border border-blue-200 overflow-x-auto">
{`{
  "name": "Иван Иванов",
  "phone": "+79991234567"
}`}
                          </pre>
                        </div>
                        <div className="mt-2">
                          <span className="font-semibold">2. GET или POST запрос с query параметрами:</span>
                          <div className="mt-1 bg-white p-2 rounded border border-blue-200 overflow-x-auto break-all overflow-wrap-anywhere">
                            <span className="font-semibold">GET</span> {settings.public_api_url}?name=Иван+Иванов&phone=+79991234567
                          </div>
                          <p className="mt-1 text-xs text-blue-600 italic break-words">
                            Примечание: GET запросы поддерживаются для удобства тестирования, но POST рекомендуется для production использования.
                          </p>
                          <p className="mt-2 text-xs text-blue-600">
                            Для добавления дополнительных полей настройте маппинг полей выше.
                          </p>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              ) : (
                <p className="text-sm text-gray-500">
                  Токен не сгенерирован. Нажмите кнопку "Сгенерировать токен" для создания публичного API endpoint.
                </p>
              )}
            </div>

            <div className="mb-6 pt-6 border-t">
              <div className="flex justify-between items-center mb-4">
                <h3 className="text-lg font-medium text-gray-900">Маппинг полей</h3>
              <button
                onClick={handleOpenFieldMappingModal}
                className="inline-flex items-center px-3 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 text-sm"
              >
                <Plus className="w-4 h-4 mr-1" />
                Добавить поле
              </button>
            </div>
            {loadingMappings ? (
              <div className="flex items-center text-gray-500">
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Загрузка маппингов...
              </div>
            ) : fieldMappings.length === 0 ? (
              <p className="text-sm text-gray-500">Маппинги полей не настроены</p>
            ) : (
              <div className="space-y-2">
                  {fieldMappings
                    .filter((m) => m.entity_type === settings.entity_type)
                    .map((mapping) => (
                      <div
                        key={mapping.id}
                        className="flex items-center justify-between p-3 bg-gray-50 rounded-md"
                      >
                        <div>
                          <span className="font-medium text-gray-900">{mapping.display_name}</span>
                          <span className="text-gray-500 mx-2">({mapping.field_name})</span>
                          <span className="text-gray-500 mx-2">→</span>
                          <span className="text-gray-700">{mapping.bitrix24_field_name}</span>
                          <span className="text-xs text-gray-500 ml-2">
                            ({mapping.bitrix24_field_id})
                          </span>
                          {mapping.update_on_event && (
                            <span className="ml-2 inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800 border border-blue-200">
                              Обновляется при событии
                            </span>
                          )}
                        </div>
                        <div className="flex space-x-2">
                          <button
                            onClick={() => handleEditFieldMapping(mapping)}
                            className="text-blue-600 hover:text-blue-800"
                            title="Редактировать"
                          >
                            <Settings2 className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => handleDeleteFieldMapping(mapping.id)}
                            className="text-red-600 hover:text-red-800"
                            title="Удалить"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      </div>
                    ))}
              </div>
            )}
          </div>
          </>
        )}

        <div className="flex justify-end space-x-3 pt-4 border-t">
          <button
            onClick={() => navigate(`/workflows/${workflowId}/leads`)}
            className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50"
            disabled={saving}
          >
            Отмена
          </button>
          <button
            onClick={handleSave}
            disabled={saving || (settings.entity_type === 'deal' && !settings.deal_stage_id)}
            className="inline-flex items-center px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {saving ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Сохранение...
              </>
            ) : (
              <>
                <Save className="w-4 h-4 mr-2" />
                Сохранить
              </>
            )}
          </button>
        </div>
      </div>

      {/* Field Mapping Modal */}
      {showFieldMappingModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl p-6 max-w-2xl w-full mx-4">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-bold text-gray-900">
                {editingMapping ? 'Редактировать маппинг поля' : 'Добавить маппинг поля'}
              </h2>
              <button
                onClick={() => {
                  setShowFieldMappingModal(false)
                  setEditingMapping(null)
                  setEditMappingData({})
                  setError(null)
                }}
                className="text-gray-400 hover:text-gray-600"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {error && (
              <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-md text-red-800 text-sm">
                {error}
              </div>
            )}

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Имя поля в системе
                </label>
                <input
                  type="text"
                  value={editingMapping ? editMappingData.field_name || '' : newMapping.field_name}
                  onChange={(e) => {
                    if (editingMapping) {
                      setEditMappingData((prev) => ({ ...prev, field_name: e.target.value }))
                    } else {
                      setNewMapping((prev) => ({ ...prev, field_name: e.target.value }))
                    }
                  }}
                  placeholder="email, company, etc."
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                />
                <p className="mt-1 text-xs text-gray-500">
                  Имя поля, которое будет использоваться при создании лидов
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Название для отображения
                </label>
                <input
                  type="text"
                  value={editingMapping ? editMappingData.display_name || '' : newMapping.display_name}
                  onChange={(e) => {
                    if (editingMapping) {
                      setEditMappingData((prev) => ({ ...prev, display_name: e.target.value }))
                    } else {
                      setNewMapping((prev) => ({ ...prev, display_name: e.target.value }))
                    }
                  }}
                  placeholder="Email, Company, etc."
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                />
                <p className="mt-1 text-xs text-gray-500">
                  Человекочитаемое название, которое будет отображаться в таблице лидов
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Поле в Bitrix24
                </label>
                {loadingFields ? (
                  <div className="flex items-center text-gray-500">
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    Загрузка полей...
                  </div>
                ) : (
                  <select
                    value={editingMapping ? editMappingData.bitrix24_field_id || '' : newMapping.bitrix24_field_id}
                    onChange={(e) => {
                      const selectedFieldId = e.target.value
                      const selectedField = fields.find((f) => f.id === selectedFieldId)
                      
                      if (editingMapping) {
                        setEditMappingData((prev) => ({
                          ...prev,
                          bitrix24_field_id: selectedFieldId,
                          // Автоматически заполняем display_name значением из Bitrix24, если оно не было изменено вручную
                          display_name: prev.display_name || selectedField?.name || '',
                        }))
                      } else {
                        setNewMapping((prev) => ({
                          ...prev,
                          bitrix24_field_id: selectedFieldId,
                          // Автоматически заполняем display_name значением из Bitrix24
                          display_name: selectedField?.name || '',
                        }))
                      }
                    }}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                  >
                    <option value="">Выберите поле из Bitrix24</option>
                    {fields.map((field) => (
                      <option key={field.id} value={field.id}>
                        {field.name} ({field.id})
                      </option>
                    ))}
                  </select>
                )}
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Тип сущности
                </label>
                <select
                  value={editingMapping ? editMappingData.entity_type || 'lead' : newMapping.entity_type}
                  onChange={(e) => {
                    const entityType = e.target.value as 'lead' | 'deal'
                    if (editingMapping) {
                      setEditMappingData((prev) => ({ ...prev, entity_type: entityType }))
                    } else {
                      setNewMapping((prev) => ({ ...prev, entity_type: entityType }))
                    }
                    loadFields(entityType)
                  }}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                >
                  <option value="lead">Лид</option>
                  <option value="deal">Сделка</option>
                </select>
              </div>

              <div>
                <label className="flex items-center">
                  <input
                    type="checkbox"
                    checked={editingMapping ? editMappingData.update_on_event || false : newMapping.update_on_event || false}
                    onChange={(e) => {
                      if (editingMapping) {
                        setEditMappingData((prev) => ({ ...prev, update_on_event: e.target.checked }))
                      } else {
                        setNewMapping((prev) => ({ ...prev, update_on_event: e.target.checked }))
                      }
                    }}
                    className="mr-2"
                  />
                  <span className="text-sm font-medium text-gray-700">
                    Обновлять это поле при событии из Bitrix24
                  </span>
                </label>
                <p className="mt-1 text-xs text-gray-500 ml-6">
                  Если включено, поле будет автоматически обновляться в базе данных при получении webhook событий от Bitrix24
                </p>
              </div>
            </div>

            <div className="flex justify-end space-x-3 mt-6 pt-4 border-t">
              <button
                onClick={() => {
                  setShowFieldMappingModal(false)
                  setEditingMapping(null)
                  setEditMappingData({})
                  setError(null)
                }}
                className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50"
              >
                Отмена
              </button>
              {editingMapping ? (
                <button
                  onClick={handleUpdateFieldMapping}
                  disabled={!editMappingData.field_name || !editMappingData.display_name}
                  className="inline-flex items-center px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <Save className="w-4 h-4 mr-2" />
                  Сохранить
                </button>
              ) : (
                <button
                  onClick={handleCreateFieldMapping}
                  disabled={!newMapping.field_name || !newMapping.display_name || !newMapping.bitrix24_field_id}
                  className="inline-flex items-center px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <Plus className="w-4 h-4 mr-2" />
                  Добавить
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

