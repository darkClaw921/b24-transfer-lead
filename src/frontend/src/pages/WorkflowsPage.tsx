import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useWorkflowStore } from '@/stores/workflowStore'
import { workflowsAPI } from '@/services/api'
import { Plus, Trash2, ArrowRight, Settings } from 'lucide-react'

interface ConversionStats {
  total: number
  successful: number
  percentage: number
}

export default function WorkflowsPage() {
  const { workflows, loading, fetchWorkflows, deleteWorkflow, createWorkflow } = useWorkflowStore()
  const [showModal, setShowModal] = useState(false)
  const [formData, setFormData] = useState({
    name: '',
    bitrix24_webhook_url: '',
  })
  const [conversionStats, setConversionStats] = useState<Record<number, ConversionStats>>({})
  const [loadingStats, setLoadingStats] = useState<Record<number, boolean>>({})
  const navigate = useNavigate()

  useEffect(() => {
    fetchWorkflows()
  }, [fetchWorkflows])

  useEffect(() => {
    // Загружаем статистику конверсии для каждого workflow
    const loadStats = async () => {
      const stats: Record<number, ConversionStats> = {}
      const loading: Record<number, boolean> = {}
      
      for (const workflow of workflows) {
        loading[workflow.id] = true
        try {
          const statsData = await workflowsAPI.getConversionStats(workflow.id)
          stats[workflow.id] = statsData
        } catch (error) {
          // Если ошибка, используем значения по умолчанию
          stats[workflow.id] = { total: 0, successful: 0, percentage: 0 }
        } finally {
          loading[workflow.id] = false
        }
      }
      
      setLoadingStats(loading)
      setConversionStats(stats)
    }

    if (workflows.length > 0) {
      loadStats()
    }
  }, [workflows])

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      await createWorkflow(formData)
      setShowModal(false)
      setFormData({ name: '', bitrix24_webhook_url: '' })
    } catch (error) {
      alert('Ошибка при создании workflow')
    }
  }

  const handleDelete = async (id: number) => {
    if (confirm('Вы уверены, что хотите удалить этот workflow?')) {
      try {
        await deleteWorkflow(id)
      } catch (error) {
        alert('Ошибка при удалении workflow')
      }
    }
  }

  if (loading) {
    return <div className="text-center py-8">Загрузка...</div>
  }

  return (
    <div className="px-4 py-6 sm:px-0">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-3xl font-bold text-gray-900">Workflows</h1>
        <button
          onClick={() => setShowModal(true)}
          className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700"
        >
          <Plus className="w-5 h-5 mr-2" />
          Создать Workflow
        </button>
      </div>

      {workflows.length === 0 ? (
        <div className="text-center py-12 bg-white rounded-lg shadow">
          <p className="text-gray-500">Нет созданных workflow</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {workflows.map((workflow) => {
            const stats = conversionStats[workflow.id]
            const isLoading = loadingStats[workflow.id]
            
            return (
              <div key={workflow.id} className="bg-white rounded-lg shadow p-6">
                <div className="flex justify-between items-start mb-2">
                  <h3 className="text-lg font-semibold text-gray-900">{workflow.name}</h3>
                  {stats && stats.total > 0 && (
                    <span className="text-sm font-bold text-blue-700">
                      {stats.percentage}%
                    </span>
                  )}
                  {isLoading && (
                    <span className="text-xs text-gray-400">...</span>
                  )}
                </div>
                <p className="text-sm text-gray-600 mb-4 truncate">{workflow.bitrix24_webhook_url}</p>
                <div className="flex justify-between items-center">
                  <button
                    onClick={() => navigate(`/workflows/${workflow.id}/leads`)}
                    className="inline-flex items-center text-sm text-blue-600 hover:text-blue-800"
                  >
                    Открыть
                    <ArrowRight className="w-4 h-4 ml-1" />
                  </button>
                  <div className="flex space-x-2">
                    <button
                      onClick={() => navigate(`/workflows/${workflow.id}/settings`)}
                      className="text-gray-600 hover:text-gray-800"
                      title="Настройки"
                    >
                      <Settings className="w-5 h-5" />
                    </button>
                    <button
                      onClick={() => handleDelete(workflow.id)}
                      className="text-red-600 hover:text-red-800"
                      title="Удалить"
                    >
                      <Trash2 className="w-5 h-5" />
                    </button>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {showModal && (
        <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50">
          <div className="relative top-20 mx-auto p-5 border w-96 shadow-lg rounded-md bg-white">
            <h3 className="text-lg font-bold text-gray-900 mb-4">Создать Workflow</h3>
            <form onSubmit={handleCreate}>
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Название
                </label>
                <input
                  type="text"
                  required
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                />
              </div>
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Webhook URL Bitrix24
                </label>
                <input
                  type="url"
                  required
                  value={formData.bitrix24_webhook_url}
                  onChange={(e) => setFormData({ ...formData, bitrix24_webhook_url: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                  placeholder="https://domain.bitrix24.ru/rest/1/token"
                />
                <p className="mt-1 text-xs text-gray-500">
                  Полный URL webhook из Bitrix24 (например: https://domain.bitrix24.ru/rest/1/7cnlev57rwpne7iq/)
                </p>
              </div>
              <div className="flex justify-end space-x-3">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50"
                >
                  Отмена
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
                >
                  Создать
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}

