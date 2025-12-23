import { useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import ProtectedRoute from './components/ProtectedRoute'
import LoginPage from './pages/LoginPage'
import WorkflowsPage from './pages/WorkflowsPage'
import LeadsPage from './pages/LeadsPage'
import WorkflowSettingsPage from './pages/WorkflowSettingsPage'
import AdminUsersPage from './pages/AdminUsersPage'
import AdminWorkflowsPage from './pages/AdminWorkflowsPage'
import { useAuthStore } from './stores/authStore'

function App() {
  const { checkAuth } = useAuthStore()

  useEffect(() => {
    // Проверяем авторизацию при загрузке приложения
    checkAuth()
  }, [checkAuth])

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <Layout>
                <Navigate to="/workflows" replace />
              </Layout>
            </ProtectedRoute>
          }
        />
        <Route
          path="/workflows"
          element={
            <ProtectedRoute>
              <Layout>
                <WorkflowsPage />
              </Layout>
            </ProtectedRoute>
          }
        />
        <Route
          path="/workflows/:id/leads"
          element={
            <ProtectedRoute>
              <Layout>
                <LeadsPage />
              </Layout>
            </ProtectedRoute>
          }
        />
        <Route
          path="/workflows/:id/settings"
          element={
            <ProtectedRoute>
              <Layout>
                <WorkflowSettingsPage />
              </Layout>
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin/users"
          element={
            <ProtectedRoute>
              <Layout>
                <AdminUsersPage />
              </Layout>
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin/workflows"
          element={
            <ProtectedRoute>
              <Layout>
                <AdminWorkflowsPage />
              </Layout>
            </ProtectedRoute>
          }
        />
      </Routes>
    </BrowserRouter>
  )
}

export default App

