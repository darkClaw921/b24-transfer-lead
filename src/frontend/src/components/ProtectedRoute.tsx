import { ReactNode } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore'

interface ProtectedRouteProps {
  children: ReactNode
}

export default function ProtectedRoute({ children }: ProtectedRouteProps) {
  const { user, loading, checkingAuth } = useAuthStore()

  // Показываем загрузку пока проверяется авторизация
  if (loading || checkingAuth) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-gray-600">Загрузка...</div>
      </div>
    )
  }

  // Редиректим на логин только после завершения проверки
  if (!user) {
    return <Navigate to="/login" replace />
  }

  return <>{children}</>
}

