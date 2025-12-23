import { useState, FormEvent, useEffect } from 'react'
import { useLeadsStore } from '@/stores/leadsStore'
import { workflowsAPI } from '@/services/api'
import type { FieldMapping, WorkflowSettings } from '@/types'
import { X } from 'lucide-react'

interface LeadFormProps {
  workflowId: number
  onClose: () => void
}

export default function LeadForm({ workflowId, onClose }: LeadFormProps) {
  const [name, setName] = useState('')
  const [phone, setPhone] = useState('')
  const [loading, setLoading] = useState(false)
  const [fieldMappings, setFieldMappings] = useState<FieldMapping[]>([])
  const [additionalFields, setAdditionalFields] = useState<Record<string, string>>({})
  const [loadingMappings, setLoadingMappings] = useState(false)
  const { createLead } = useLeadsStore()

  useEffect(() => {
    loadFieldMappings()
  }, [workflowId])

  const loadFieldMappings = async () => {
    try {
      setLoadingMappings(true)
      const settings: WorkflowSettings = await workflowsAPI.getSettings(workflowId)
      const mappings = await workflowsAPI.getFieldMappings(workflowId)
      // Фильтруем маппинги по типу сущности
      const filtered = mappings.filter((m) => m.entity_type === settings.entity_type)
      setFieldMappings(filtered)
      
      // Инициализируем дополнительные поля
      const fields: Record<string, string> = {}
      filtered.forEach((mapping) => {
        fields[mapping.field_name] = ''
      })
      setAdditionalFields(fields)
    } catch (error) {
      console.error('Failed to load field mappings:', error)
    } finally {
      setLoadingMappings(false)
    }
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setLoading(true)

    try {
      const leadData: Record<string, string> = { phone, name }
      // Добавляем дополнительные поля
      Object.entries(additionalFields).forEach(([key, value]) => {
        if (value.trim()) {
          leadData[key] = value
        }
      })
      await createLead(workflowId, phone, name, leadData)
      setName('')
      setPhone('')
      setAdditionalFields(
        Object.fromEntries(fieldMappings.map((m) => [m.field_name, '']))
      )
      onClose()
    } catch (error) {
      alert('Ошибка при создании лида')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50">
      <div className="relative top-20 mx-auto p-5 border w-96 shadow-lg rounded-md bg-white">
        <div className="flex justify-between items-center mb-4">
          <h3 className="text-lg font-bold text-gray-900">Добавить лид</h3>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
        <form onSubmit={handleSubmit}>
          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Имя
            </label>
            <input
              type="text"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-blue-500 focus:border-blue-500"
            />
          </div>
          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Телефон
            </label>
            <input
              type="tel"
              required
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-blue-500 focus:border-blue-500"
            />
          </div>
          {loadingMappings ? (
            <div className="mb-4 text-sm text-gray-500">Загрузка полей...</div>
          ) : (
            fieldMappings.map((mapping) => (
              <div key={mapping.id} className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {mapping.display_name}
                </label>
                <input
                  type="text"
                  value={additionalFields[mapping.field_name] || ''}
                  onChange={(e) =>
                    setAdditionalFields((prev) => ({
                      ...prev,
                      [mapping.field_name]: e.target.value,
                    }))
                  }
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                />
              </div>
            ))
          )}
          <div className="flex justify-end space-x-3">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50"
            >
              Отмена
            </button>
            <button
              type="submit"
              disabled={loading}
              className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
            >
              {loading ? 'Создание...' : 'Создать'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

