import { useState, useMemo } from 'react'
import { useLeadsStore } from '@/stores/leadsStore'
import type { Lead } from '@/types'
import { ArrowUpDown, ArrowUp, ArrowDown } from 'lucide-react'

interface LeadsTableProps {
  workflowId: number
  statusMap: Record<string, string> // Маппинг ID статуса -> название
  fieldMappings?: Record<string, { display_name: string; bitrix24_field_name: string }> // Маппинг field_name -> { display_name, bitrix24_field_name }
}

type SortField = 'name' | 'phone' | 'status' | 'created_at'
type SortDirection = 'asc' | 'desc'

export default function LeadsTable({ workflowId: _workflowId, statusMap, fieldMappings = {} }: LeadsTableProps) {
  const { leads } = useLeadsStore()
  const [sortField, setSortField] = useState<SortField>('created_at')
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc')
  const [filterStatus, setFilterStatus] = useState<string>('')
  const [filterName, setFilterName] = useState<string>('')

  const sortedAndFilteredLeads = useMemo(() => {
    let filtered = leads.filter((lead) => {
      const matchesStatus = !filterStatus || lead.status === filterStatus
      const matchesName =
        !filterName || lead.name.toLowerCase().includes(filterName.toLowerCase())
      return matchesStatus && matchesName
    })

    filtered.sort((a, b) => {
      let aValue: string | number
      let bValue: string | number

      switch (sortField) {
        case 'name':
          aValue = a.name
          bValue = b.name
          break
        case 'phone':
          aValue = a.phone
          bValue = b.phone
          break
        case 'status':
          aValue = a.status || ''
          bValue = b.status || ''
          break
        case 'created_at':
          aValue = new Date(a.created_at).getTime()
          bValue = new Date(b.created_at).getTime()
          break
        default:
          return 0
      }

      if (aValue < bValue) return sortDirection === 'asc' ? -1 : 1
      if (aValue > bValue) return sortDirection === 'asc' ? 1 : -1
      return 0
    })

    return filtered
  }, [leads, sortField, sortDirection, filterStatus, filterName])

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc')
    } else {
      setSortField(field)
      setSortDirection('asc')
    }
  }

  const SortIcon = ({ field }: { field: SortField }) => {
    if (sortField !== field) {
      return <ArrowUpDown className="w-4 h-4 ml-1 inline" />
    }
    return sortDirection === 'asc' ? (
      <ArrowUp className="w-4 h-4 ml-1 inline" />
    ) : (
      <ArrowDown className="w-4 h-4 ml-1 inline" />
    )
  }

  const uniqueStatuses = useMemo(() => {
    const statuses = new Set(leads.map((lead) => lead.status).filter(Boolean))
    return Array.from(statuses) as string[]
  }, [leads])

  // Функция для получения названия статуса по ID
  const getStatusName = (statusId: string | null): string => {
    if (!statusId) return 'NEW'
    return statusMap[statusId] || statusId
  }

  // Функция для получения классов цвета статуса на основе семантического ID
  const getStatusColorClasses = (semanticId: string | null): string => {
    if (semanticId === 'S') {
      return 'bg-green-100 text-green-800'  // Успешный статус - зеленый
    } else if (semanticId === 'F') {
      return 'bg-red-100 text-red-800'  // Неуспешный статус - красный
    }
    return 'bg-blue-100 text-blue-800'  // По умолчанию - синий
  }

  // Получить все дополнительные поля из маппингов (а не только из лидов)
  // Это гарантирует, что все настроенные поля будут отображаться в таблице
  const additionalFields = useMemo(() => {
    // Используем маппинги как источник истины для отображаемых полей
    const fieldsFromMappings = Object.keys(fieldMappings)
    
    // Также добавляем поля, которые есть в лидах, но еще не в маппингах (на случай, если маппинги не загружены)
    const fieldsSet = new Set<string>(fieldsFromMappings)
    leads.forEach((lead) => {
      lead.fields?.forEach((field) => {
        fieldsSet.add(field.field_name)
      })
    })
    return Array.from(fieldsSet)
  }, [leads, fieldMappings])

  // Получить значение поля для лида
  const getFieldValue = (lead: Lead, fieldName: string): string => {
    const field = lead.fields?.find((f) => f.field_name === fieldName)
    return field?.field_value || '-'
  }

  // Получить отображаемое название поля
  const getFieldDisplayName = (fieldName: string): string => {
    const mapping = fieldMappings[fieldName]
    if (mapping) {
      // Используем display_name, если оно задано и не пустое, иначе bitrix24_field_name
      const displayName = mapping.display_name?.trim()
      return displayName || mapping.bitrix24_field_name || fieldName
    }
    return fieldName
  }

  return (
    <div className="bg-white shadow rounded-lg overflow-hidden">
      <div className="p-4 border-b border-gray-200">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Фильтр по имени
            </label>
            <input
              type="text"
              value={filterName}
              onChange={(e) => setFilterName(e.target.value)}
              placeholder="Поиск по имени..."
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-blue-500 focus:border-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Фильтр по статусу
            </label>
            <select
              value={filterStatus}
              onChange={(e) => setFilterStatus(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="">Все статусы</option>
              {uniqueStatuses.map((status) => (
                <option key={status} value={status}>
                  {getStatusName(status)}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th
                className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100"
                onClick={() => handleSort('name')}
              >
                Имя
                <SortIcon field="name" />
              </th>
              <th
                className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100"
                onClick={() => handleSort('phone')}
              >
                Телефон
                <SortIcon field="phone" />
              </th>
              <th
                className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100"
                onClick={() => handleSort('status')}
              >
                Статус
                <SortIcon field="status" />
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Ответственный
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Bitrix24 ID
              </th>
              {additionalFields.map((fieldName) => (
                <th
                  key={fieldName}
                  className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
                >
                  {getFieldDisplayName(fieldName)}
                </th>
              ))}
              <th
                className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100"
                onClick={() => handleSort('created_at')}
              >
                Создан
                <SortIcon field="created_at" />
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {sortedAndFilteredLeads.length === 0 ? (
              <tr>
                <td colSpan={6 + additionalFields.length} className="px-6 py-4 text-center text-gray-500">
                  Нет лидов
                </td>
              </tr>
            ) : (
              sortedAndFilteredLeads.map((lead) => (
                <tr key={lead.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                    {lead.name}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {lead.phone}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${getStatusColorClasses(lead.status_semantic_id)}`}>
                      {getStatusName(lead.status)}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {lead.assigned_by_name || '-'}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {lead.bitrix24_lead_id || '-'}
                  </td>
                  {additionalFields.map((fieldName) => (
                    <td key={fieldName} className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {getFieldValue(lead, fieldName)}
                    </td>
                  ))}
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {new Date(lead.created_at).toLocaleString('ru-RU')}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

