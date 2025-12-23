import { useEffect, useState, useRef } from 'react'
import { useParams } from 'react-router-dom'
import { useLeadsStore } from '@/stores/leadsStore'
import { workflowsAPI, leadsAPI } from '@/services/api'
import type { WorkflowSettings, Status } from '@/types'
import LeadsTable from '@/components/LeadsTable'
import LeadForm from '@/components/LeadForm'
import CSVUpload from '@/components/CSVUpload'

export default function LeadsPage() {
  const { id } = useParams<{ id: string }>()
  const workflowId = parseInt(id || '0', 10)
  const { loading, leads, fetchLeads } = useLeadsStore()
  const [showForm, setShowForm] = useState(false)
  const [showCSVUpload, setShowCSVUpload] = useState(false)
  const [statusMap, setStatusMap] = useState<Record<string, string>>({})
  const [fieldMappings, setFieldMappings] = useState<Record<string, { display_name: string; bitrix24_field_name: string }>>({})
  const lastFetchedWorkflowId = useRef<number | null>(null)

  // Вычисление статистики конверсии
  const conversionStats = (() => {
    const totalLeads = leads.length
    if (totalLeads === 0) return { percentage: 0, successful: 0, total: 0 }
    
    const successfulLeads = leads.filter(lead => lead.status_semantic_id === 'S').length
    const percentage = (successfulLeads / totalLeads) * 100
    
    return {
      percentage: Math.round(percentage * 100) / 100, // Округление до 2 знаков после запятой
      successful: successfulLeads,
      total: totalLeads
    }
  })()

  useEffect(() => {
    if (workflowId && workflowId !== lastFetchedWorkflowId.current && !loading) {
      lastFetchedWorkflowId.current = workflowId
      fetchLeads(workflowId)
      loadStatusMap(workflowId)
      loadFieldMappings(workflowId)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workflowId])

  const loadStatusMap = async (id: number) => {
    try {
      const settings: WorkflowSettings = await workflowsAPI.getSettings(id)
      let statuses: Status[] = []

      if (settings.entity_type === 'lead') {
        // Загружаем статусы лидов
        statuses = await workflowsAPI.getLeadStatuses(id)
      } else if (settings.entity_type === 'deal') {
        // Загружаем стадии сделок для выбранной воронки
        const categoryId = settings.deal_category_id ?? 0
        statuses = await workflowsAPI.getStages(id, categoryId)
      }

      // Создаем маппинг ID -> название
      const map: Record<string, string> = {}
      statuses.forEach((status) => {
        map[status.id] = status.name
      })
      setStatusMap(map)
    } catch (error) {
      console.error('Failed to load status map:', error)
      // В случае ошибки используем пустой маппинг
      setStatusMap({})
    }
  }

  const loadFieldMappings = async (id: number) => {
    try {
      const mappings = await workflowsAPI.getFieldMappings(id)
      const map: Record<string, { display_name: string; bitrix24_field_name: string }> = {}
      mappings.forEach((mapping) => {
        map[mapping.field_name] = {
          display_name: mapping.display_name,
          bitrix24_field_name: mapping.bitrix24_field_name,
        }
      })
      setFieldMappings(map)
    } catch (error) {
      console.error('Failed to load field mappings:', error)
      setFieldMappings({})
    }
  }

  return (
    <div className="px-4 py-6 sm:px-0">
      <div className="flex justify-between items-center mb-6">
        <div className="flex items-center gap-4">
          <h1 className="text-3xl font-bold text-gray-900">Лиды</h1>
          {leads.length > 0 && (
            <div className="flex items-center gap-2 px-3 py-1.5 bg-blue-50 rounded-lg border border-blue-200">
              <span className="text-sm font-medium text-gray-700">Конверсия:</span>
              <span className="text-sm font-bold text-blue-700">{conversionStats.percentage}%</span>
              <span className="text-xs text-gray-500">
                ({conversionStats.successful}/{conversionStats.total})
              </span>
            </div>
          )}
        </div>
        <div className="flex space-x-3">
          {leads.length > 0 && (
            <button
              onClick={() => leadsAPI.exportCSV(workflowId)}
              className="inline-flex items-center px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
            >
              Экспорт в CSV
            </button>
          )}
          <button
            onClick={() => setShowCSVUpload(true)}
            className="inline-flex items-center px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
          >
            Загрузить CSV
          </button>
          <button
            onClick={() => setShowForm(true)}
            className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700"
          >
            Добавить лид
          </button>
        </div>
      </div>

      {loading ? (
        <div className="text-center py-8">Загрузка...</div>
      ) : (
        <LeadsTable workflowId={workflowId} statusMap={statusMap} fieldMappings={fieldMappings} />
      )}

      {showForm && (
        <LeadForm workflowId={workflowId} onClose={() => setShowForm(false)} />
      )}

      {showCSVUpload && (
        <CSVUpload workflowId={workflowId} onClose={() => setShowCSVUpload(false)} />
      )}
    </div>
  )
}

