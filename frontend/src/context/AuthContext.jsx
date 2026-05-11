/**
 * @file AuthContext.jsx
 * @description Core React component/service for the Project Nexus application.
 */

import { createContext, useContext, useState, useEffect, useCallback } from 'react'
import { authAPI } from '../services/api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    const saved = localStorage.getItem('user')
    return saved ? JSON.parse(saved) : null
  })
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const token = localStorage.getItem('access_token')
    if (!token) {
      setUser(null)
      setLoading(false)
      return
    }

    authAPI.me()
      .then(({ data }) => {
        if (data.success) {
          setUser(data.data)
          localStorage.setItem('user', JSON.stringify(data.data))
        }
      })
      .catch(() => {
        localStorage.clear()
        setUser(null)
      })
      .finally(() => setLoading(false))
  }, [])

  const login = useCallback(async (email, password) => {
    const { data } = await authAPI.login(email, password)
    if (data.success) {
      const { access_token, refresh_token, user: userData } = data.data
      localStorage.setItem('access_token', access_token)
      localStorage.setItem('refresh_token', refresh_token)
      localStorage.setItem('user', JSON.stringify(userData))
      setUser(userData)
      return userData
    }
    throw new Error(data.error?.message || 'Login failed')
  }, [])

  const logout = useCallback(async () => {
    try {
      await authAPI.logout()
    } catch {
      // ignore
    }
    localStorage.clear()
    setUser(null)
  }, [])

  const isAdmin = user?.roles?.includes('admin')
  const isCeo = user?.roles?.includes('ceo')
  const isManager = user?.roles?.includes('manager')
  const isManagement = isAdmin || isCeo || isManager

  return (
    <AuthContext.Provider
      value={{ user, login, logout, loading, isAdmin, isCeo, isManager, isManagement }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
