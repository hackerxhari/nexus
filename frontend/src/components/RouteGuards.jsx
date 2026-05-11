/**
 * @file RouteGuards.jsx
 * @description Core React component/service for the Project Nexus application.
 */

import { Navigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { motion } from 'framer-motion'
import './RouteGuards.css'

export function ProtectedRoute({ children, adminOnly = false, managementOnly = false }) {
  const { user, loading, isAdmin, isManagement } = useAuth()

  if (loading) {
    return (
      <div className="route-loading">
        <motion.div
          className="route-loading__spinner"
          animate={{ rotate: 360 }}
          transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
        />
      </div>
    )
  }

  if (!user) return <Navigate to="/login" replace />
  if (adminOnly && !isAdmin) return <Navigate to="/" replace />
  if (managementOnly && !isManagement) return <Navigate to="/" replace />

  return children
}

export function PublicRoute({ children }) {
  const { user, loading } = useAuth()

  if (loading) return null
  if (user) return <Navigate to="/" replace />

  return children
}
