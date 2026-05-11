/**
 * @file App.jsx
 * @description Core React component/service for the Project Nexus application.
 */

import { lazy, Suspense } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import { AuthProvider } from './context/AuthContext'
import { ProtectedRoute, PublicRoute } from './components/RouteGuards'
import Layout from './components/Layout'
import './index.css'

// Lazy-loaded pages — each gets its own chunk
const LandingPage = lazy(() => import('./landing/LandingPage'))
const LoginPage = lazy(() => import('./pages/LoginPage'))
const QueryPage = lazy(() => import('./pages/QueryPage'))
const DocumentsPage = lazy(() => import('./pages/DocumentsPage'))
const UploadPage = lazy(() => import('./pages/UploadPage'))
const HistoryPage = lazy(() => import('./pages/HistoryPage'))
const UsersPage = lazy(() => import('./pages/UsersPage'))
const AuditPage = lazy(() => import('./pages/AuditPage'))
const CustomQAPage = lazy(() => import('./pages/CustomQAPage'))
const DepartmentsPage = lazy(() => import('./pages/DepartmentsPage'))

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Toaster
          position="top-right"
          toastOptions={{
            duration: 3000,
            style: {
              background: '#141418',
              color: '#f0f0f2',
              border: '1px solid rgba(255,255,255,0.06)',
              borderRadius: '12px',
              fontSize: '0.85rem',
              boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
            },
            success: {
              iconTheme: { primary: '#22c55e', secondary: '#0a0a0b' },
            },
            error: {
              iconTheme: { primary: '#ef4444', secondary: '#0a0a0b' },
            },
          }}
        />
        <Suspense fallback={
          <div style={{
            height: '100vh', display: 'flex', alignItems: 'center',
            justifyContent: 'center', background: '#0a0a0b', color: '#71717a',
            fontSize: '0.85rem', letterSpacing: '0.1em',
          }}>LOADING…</div>
        }>
          <Routes>
            {/* Landing page — public */}
            <Route path="/landing" element={<LandingPage />} />

            {/* Public */}
            <Route path="/login" element={
              <PublicRoute><LoginPage /></PublicRoute>
            } />

            {/* Protected — with sidebar layout */}
            <Route element={
              <ProtectedRoute><Layout /></ProtectedRoute>
            }>
              <Route index element={<QueryPage />} />
              <Route path="documents" element={<DocumentsPage />} />
              <Route path="history" element={<HistoryPage />} />
              <Route path="upload" element={<UploadPage />} />
              <Route path="users" element={
                <ProtectedRoute managementOnly><UsersPage /></ProtectedRoute>
              } />
              <Route path="audit" element={
                <ProtectedRoute managementOnly><AuditPage /></ProtectedRoute>
              } />
              <Route path="custom-qa" element={
                <ProtectedRoute adminOnly><CustomQAPage /></ProtectedRoute>
              } />
              <Route path="departments" element={
                <ProtectedRoute adminOnly><DepartmentsPage /></ProtectedRoute>
              } />
            </Route>
          </Routes>
        </Suspense>
      </BrowserRouter>
    </AuthProvider>
  )
}
