import { useState, FormEvent, useEffect } from 'react'
import { useLeadsStore } from '@/stores/leadsStore'
import { workflowsAPI } from '@/services/api'
import type { FieldMapping } from '@/types'
import { X, Upload } from 'lucide-react'

interface CSVUploadProps {
  workflowId: number
  onClose: () => void
}

export default function CSVUpload({ workflowId, onClose }: CSVUploadProps) {
  const [file, setFile] = useState<File | null>(null)
  const [csvHeaders, setCsvHeaders] = useState<string[]>([])
  const [csvRowCount, setCsvRowCount] = useState<number>(0)
  const [fieldMappings, setFieldMappings] = useState<FieldMapping[]>([])
  const [columnMapping, setColumnMapping] = useState<Record<string, string>>({})
  const [processAllRows, setProcessAllRows] = useState<boolean>(true)
  const [rowsToProcess, setRowsToProcess] = useState<number>(1)
  const [loading, setLoading] = useState(false)
  const [loadingMappings, setLoadingMappings] = useState(false)
  const [uploadProgress, setUploadProgress] = useState<number>(0)
  const [estimatedTimeRemaining, setEstimatedTimeRemaining] = useState<number | null>(null)
  const { uploadCSV } = useLeadsStore()

  useEffect(() => {
    loadFieldMappings()
  }, [workflowId])

  const loadFieldMappings = async () => {
    try {
      setLoadingMappings(true)
      const settings = await workflowsAPI.getSettings(workflowId)
      const mappings = await workflowsAPI.getFieldMappings(workflowId)
      // Фильтруем маппинги по типу сущности
      const filtered = mappings.filter((m) => m.entity_type === settings.entity_type)
      setFieldMappings(filtered)
    } catch (error) {
      console.error('Failed to load field mappings:', error)
    } finally {
      setLoadingMappings(false)
    }
  }

  const parseCSVHeaders = async (file: File) => {
    return new Promise<{ headers: string[]; rowCount: number }>((resolve, reject) => {
      const reader = new FileReader()
      reader.onload = (e) => {
        try {
          const text = e.target?.result as string
          const lines = text.split(/\r?\n/).filter((line) => line.trim().length > 0)
          if (lines.length === 0) {
            reject(new Error('CSV файл пуст'))
            return
          }
          // Простой парсинг CSV заголовков с поддержкой кавычек
          const firstLine = lines[0]
          const headers: string[] = []
          let currentHeader = ''
          let inQuotes = false
          
          for (let i = 0; i < firstLine.length; i++) {
            const char = firstLine[i]
            if (char === '"') {
              inQuotes = !inQuotes
            } else if (char === ',' && !inQuotes) {
              headers.push(currentHeader.trim())
              currentHeader = ''
            } else {
              currentHeader += char
            }
          }
          headers.push(currentHeader.trim())
          
          // Убираем кавычки из заголовков
          const cleanedHeaders = headers.map((h) => h.replace(/^"|"$/g, ''))
          // Количество строк данных (без заголовка)
          const rowCount = Math.max(0, lines.length - 1)
          resolve({ headers: cleanedHeaders, rowCount })
        } catch (error) {
          reject(error)
        }
      }
      reader.onerror = reject
      reader.readAsText(file)
    })
  }

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0]
    if (!selectedFile) {
      setFile(null)
      setCsvHeaders([])
      setColumnMapping({})
      return
    }

    setFile(selectedFile)
    try {
      const { headers, rowCount } = await parseCSVHeaders(selectedFile)
      setCsvHeaders(headers)
      setCsvRowCount(rowCount)
      setRowsToProcess(Math.min(rowCount, 10)) // По умолчанию обрабатываем 10 строк или меньше
      
      // Автоматически маппим phone и name, если найдены соответствующие колонки
      const autoMapping: Record<string, string> = {}
      headers.forEach((header) => {
        const headerLower = header.toLowerCase().trim()
        if (['phone', 'телефон', 'tel', 'номер'].includes(headerLower)) {
          autoMapping[header] = 'phone'
        } else if (['name', 'имя', 'fio', 'фио'].includes(headerLower)) {
          autoMapping[header] = 'name'
        }
      })
      setColumnMapping(autoMapping)
    } catch (error) {
      alert('Ошибка при чтении CSV файла: ' + (error instanceof Error ? error.message : 'Неизвестная ошибка'))
      setFile(null)
      setCsvHeaders([])
      setCsvRowCount(0)
    }
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!file) return

    // Проверка валидности маппинга
    const hasPhone = Object.values(columnMapping).includes('phone')
    const hasName = Object.values(columnMapping).includes('name')
    if (!hasPhone || !hasName) {
      alert('Необходимо выбрать маппинг для обязательных полей: phone и name')
      return
    }

    setLoading(true)
    setUploadProgress(0)
    setEstimatedTimeRemaining(null)
    const startTimeValue = Date.now()
    let uploadCompleted = false
    let fileUploadProgress = 0
    
    // Симуляция прогресса обработки (начинается после загрузки файла)
    let processingProgress = 50 // Начинаем с 50% после загрузки файла
    const totalRows = processAllRows ? csvRowCount : rowsToProcess
    // Оценка времени обработки: примерно 1-2 секунды на строку
    const estimatedProcessingTime = totalRows * 1.5 // секунды
    
    const processingInterval = setInterval(() => {
      if (!uploadCompleted) {
        // Пока файл загружается, не трогаем прогресс обработки
        return
      }
      
      // После загрузки файла медленно увеличиваем прогресс обработки
      const elapsed = (Date.now() - startTimeValue) / 1000
      const processingElapsed = elapsed - (fileUploadProgress > 0 ? (fileUploadProgress / 50) * elapsed : 0)
      
      // Медленно увеличиваем прогресс от 50% до 95%
      // Используем логарифмическую функцию для более реалистичного прогресса
      if (processingProgress < 95) {
        // Увеличиваем прогресс медленно, основываясь на прошедшем времени
        const targetProgress = 50 + (45 * Math.min(processingElapsed / estimatedProcessingTime, 0.95))
        processingProgress = Math.min(targetProgress, 95)
        setUploadProgress(processingProgress)
        
        // Расчет оставшегося времени
        if (processingElapsed > 0 && processingProgress < 95) {
          const rate = (processingProgress - 50) / processingElapsed
          if (rate > 0) {
            const remaining = (95 - processingProgress) / rate
            setEstimatedTimeRemaining(Math.max(0, Math.ceil(remaining)))
          }
        }
      }
    }, 100) // Обновляем каждые 100мс

    try {
      const limit = processAllRows ? null : rowsToProcess
      await uploadCSV(workflowId, file, columnMapping, limit, (progress) => {
        // Прогресс загрузки файла (0-50%)
        fileUploadProgress = (progress.loaded / progress.total) * 50
        setUploadProgress(fileUploadProgress)
        
        // Расчет оставшегося времени для загрузки
        const elapsed = (Date.now() - startTimeValue) / 1000
        if (progress.loaded > 0 && elapsed > 0) {
          const rate = fileUploadProgress / elapsed
          if (rate > 0) {
            const remaining = (50 - fileUploadProgress) / rate
            setEstimatedTimeRemaining(Math.max(0, Math.ceil(remaining)))
          }
        }
      })
      
      // Файл загружен, начинаем обработку
      uploadCompleted = true
      processingProgress = 50
      setUploadProgress(50)
      
      // Ждем завершения обработки на сервере
      // Прогресс будет медленно увеличиваться до 95% пока идет обработка
      
      // После завершения обработки быстро завершаем до 100%
      clearInterval(processingInterval)
      setUploadProgress(100)
      setEstimatedTimeRemaining(0)
      
      // Небольшая задержка перед закрытием, чтобы пользователь увидел 100%
      await new Promise(resolve => setTimeout(resolve, 500))
      
      setFile(null)
      setCsvHeaders([])
      setCsvRowCount(0)
      setColumnMapping({})
      setProcessAllRows(true)
      setRowsToProcess(1)
      onClose()
    } catch (error) {
      clearInterval(processingInterval)
      alert('Ошибка при загрузке CSV файла')
    } finally {
      setLoading(false)
      setUploadProgress(0)
      setEstimatedTimeRemaining(null)
    }
  }

  // Проверка валидности маппинга для активации кнопки
  const isValidMapping = () => {
    const hasPhone = Object.values(columnMapping).includes('phone')
    const hasName = Object.values(columnMapping).includes('name')
    return hasPhone && hasName
  }

  return (
    <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50">
      <div className="relative top-10 mx-auto p-5 border w-full max-w-2xl shadow-lg rounded-md bg-white max-h-[90vh] overflow-y-auto">
        <div className="flex justify-between items-center mb-4">
          <h3 className="text-lg font-bold text-gray-900">Загрузить CSV</h3>
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
              CSV файл
            </label>
            <div className="mt-1 flex justify-center px-6 pt-5 pb-6 border-2 border-gray-300 border-dashed rounded-md">
              <div className="space-y-1 text-center">
                <Upload className="mx-auto h-12 w-12 text-gray-400" />
                <div className="flex text-sm text-gray-600">
                  <label className="relative cursor-pointer bg-white rounded-md font-medium text-blue-600 hover:text-blue-500">
                    <span>Выберите файл</span>
                    <input
                      type="file"
                      accept=".csv"
                      required
                      onChange={handleFileChange}
                      className="sr-only"
                    />
                  </label>
                  <p className="pl-1">или перетащите сюда</p>
                </div>
                {file && (
                  <p className="text-xs text-gray-500 mt-2">{file.name}</p>
                )}
              </div>
            </div>
          </div>

          {csvHeaders.length > 0 && !loadingMappings && (
            <>
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Маппинг колонок CSV на поля
                </label>
                <div className="space-y-2 max-h-64 overflow-y-auto border rounded-md p-3">
                  {csvHeaders.map((csvColumn) => (
                    <div key={csvColumn} className="flex items-center space-x-2">
                      <label className="flex-1 text-sm text-gray-700 min-w-[150px]">
                        {csvColumn}:
                      </label>
                      <select
                        value={columnMapping[csvColumn] || ''}
                        onChange={(e) => {
                          const value = e.target.value
                          if (value) {
                            setColumnMapping({ ...columnMapping, [csvColumn]: value })
                          } else {
                            const newMapping = { ...columnMapping }
                            delete newMapping[csvColumn]
                            setColumnMapping(newMapping)
                          }
                        }}
                        className="flex-1 border border-gray-300 rounded-md px-3 py-1 text-sm"
                      >
                        <option value="">-- Не использовать --</option>
                        <option value="phone">Телефон (phone)</option>
                        <option value="name">Имя (name)</option>
                        {fieldMappings.map((mapping) => (
                          <option key={mapping.id} value={mapping.field_name}>
                            {mapping.display_name} ({mapping.field_name})
                          </option>
                        ))}
                      </select>
                    </div>
                  ))}
                </div>
                <p className="mt-2 text-xs text-gray-500">
                  Выберите, какие колонки CSV соответствуют каким полям. Обязательные поля: phone и name.
                </p>
              </div>

              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Количество строк для обработки
                </label>
                <div className="space-y-2">
                  <div className="flex items-center space-x-2">
                    <input
                      type="radio"
                      id="processAll"
                      name="processRows"
                      checked={processAllRows}
                      onChange={() => setProcessAllRows(true)}
                      className="w-4 h-4 text-blue-600"
                    />
                    <label htmlFor="processAll" className="text-sm text-gray-700">
                      Обработать все строки ({csvRowCount} строк)
                    </label>
                  </div>
                  <div className="flex items-center space-x-2">
                    <input
                      type="radio"
                      id="processLimited"
                      name="processRows"
                      checked={!processAllRows}
                      onChange={() => setProcessAllRows(false)}
                      className="w-4 h-4 text-blue-600"
                    />
                    <label htmlFor="processLimited" className="text-sm text-gray-700 flex items-center space-x-2">
                      <span>Обработать</span>
                      <input
                        type="number"
                        min="1"
                        max={csvRowCount}
                        value={rowsToProcess}
                        onChange={(e) => {
                          const value = parseInt(e.target.value, 10)
                          if (!isNaN(value) && value >= 1 && value <= csvRowCount) {
                            setRowsToProcess(value)
                          }
                        }}
                        disabled={processAllRows}
                        className="w-20 border border-gray-300 rounded-md px-2 py-1 text-sm disabled:bg-gray-100 disabled:cursor-not-allowed"
                      />
                      <span>строк</span>
                    </label>
                  </div>
                </div>
              </div>
            </>
          )}

          {loadingMappings && (
            <div className="mb-4 text-center text-sm text-gray-500">
              Загрузка маппингов полей...
            </div>
          )}

          {loading && (
            <div className="mb-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium text-gray-700">Загрузка CSV файла...</span>
                <span className="text-sm text-gray-500">
                  {processAllRows ? csvRowCount : rowsToProcess} строк
                  {estimatedTimeRemaining !== null && estimatedTimeRemaining > 0 && (
                    <span className="ml-2">• Осталось ~{estimatedTimeRemaining}с</span>
                  )}
                </span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2.5">
                <div
                  className="bg-blue-600 h-2.5 rounded-full transition-all duration-300 ease-out"
                  style={{ width: `${uploadProgress}%` }}
                />
              </div>
              <div className="flex items-center justify-between mt-1">
                <p className="text-xs text-gray-500">
                  {uploadProgress < 50 
                    ? 'Загрузка файла на сервер...' 
                    : uploadProgress < 100
                    ? 'Обработка данных и создание лидов в Bitrix24...'
                    : 'Завершено!'}
                </p>
                <span className="text-xs font-medium text-gray-700">{Math.round(uploadProgress)}%</span>
              </div>
            </div>
          )}

          <div className="flex justify-end space-x-3">
            <button
              type="button"
              onClick={onClose}
              disabled={loading}
              className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Отмена
            </button>
            <button
              type="submit"
              disabled={loading || !file || !isValidMapping()}
              className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? 'Загрузка...' : 'Загрузить'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

