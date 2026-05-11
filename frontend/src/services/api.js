/**
 * @file api.js
 * @description Core React component/service for the Project Nexus application.
 */

import axios from 'axios'

const api = axios.create({
  baseURL: '/api/v1',
  headers: { 'Content-Type': 'application/json' },
})

// Attach token to every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Handle 401 — try refresh, else logout
api.interceptors.response.use(
  (res) => res,
  async (error) => {
    const original = error.config
    if (error.response?.status === 401 && !original._retry) {
      original._retry = true
      const refresh = localStorage.getItem('refresh_token')
      if (refresh) {
        try {
          const { data } = await axios.post('/api/v1/auth/refresh', {
            refresh_token: refresh,
          })
          if (data.success) {
            localStorage.setItem('access_token', data.data.access_token)
            original.headers.Authorization = `Bearer ${data.data.access_token}`
            return api(original)
          }
        } catch {
          // refresh failed
        }
      }
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      localStorage.removeItem('user')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

// ── Auth ──────────────────────────────────
export const authAPI = {
  login: (email, password) =>
    api.post('/auth/login', { email, password }),

  logout: () => {
    const refreshToken = localStorage.getItem('refresh_token')
    return api.post('/auth/logout', {}, {
      headers: { 'X-Refresh-Token': refreshToken },
    })
  },

  refresh: (refresh_token) =>
    api.post('/auth/refresh', { refresh_token }),

  me: () => api.get('/auth/me'),
}

// ── Query ─────────────────────────────────
export const queryAPI = {
  ask: (question, departmentFilter = null, bypassCache = false, conversationHistory = null) =>
    api.post('/query/ask', {
      question,
      department_filter: departmentFilter,
      bypass_cache: bypassCache,
      conversation_history: conversationHistory,
    }),

  history: (skip = 0, limit = 50) =>
    api.get(`/query/history?skip=${skip}&limit=${limit}`),
}

// ── Documents ─────────────────────────────
export const docsAPI = {
  upload: (file, allowedRoles, departmentsStr, documentName) => {
    const form = new FormData()
    form.append('file', file)
    form.append('allowed_roles', allowedRoles)
    if (departmentsStr) form.append('departments', departmentsStr)
    if (documentName) form.append('document_name', documentName)
    return api.post('/documents/upload', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },

  list: (skip = 0, limit = 50, department, status) => {
    const params = new URLSearchParams({ skip, limit })
    if (department) params.append('department', department)
    if (status) params.append('status', status)
    return api.get(`/documents/?${params}`)
  },

  delete: (docId) => api.delete(`/documents/${docId}`),

  clearAll: (deleteFiles = false) =>
    api.delete(`/documents/clear-all?delete_files=${deleteFiles}`),

  pruneMissing: () => api.post('/documents/prune-missing'),
}

// ── Query Debug ──────────────────────────
export const queryDebugAPI = {
  contains: (q, filename = null, docId = null, limit = 200) => {
    const params = new URLSearchParams({ q, limit })
    if (filename) params.append('filename', filename)
    if (docId) params.append('doc_id', docId)
    return api.get(`/query/debug/contains?${params}`)
  },
}

// ── Admin ─────────────────────────────────
export const adminAPI = {
  createUser: (data) => api.post('/admin/users', data),
  listUsers: (skip = 0, limit = 50) =>
    api.get(`/admin/users?skip=${skip}&limit=${limit}`),
  updateRoles: (userId, roles) =>
    api.patch(`/admin/users/${userId}/roles`, { roles }),
  deactivateUser: (userId) =>
    api.patch(`/admin/users/${userId}/deactivate`),
  deleteUser: (userId) =>
    api.delete(`/admin/users/${userId}`),
  auditLogs: (skip = 0, limit = 100) =>
    api.get(`/admin/audit-logs?skip=${skip}&limit=${limit}`),
  health: () => api.get('/admin/health'),
}

// ── STT (Speech-to-Text) ──────────────────
export const sttAPI = {
  transcribe: (audioBlob) => {
    const form = new FormData()
    form.append('audio', audioBlob, 'recording.wav')
    return api.post('/stt/transcribe', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  status: () => api.get('/stt/status'),
}

// ── Custom Q&A ────────────────────────────
export const customQaAPI = {
  list: (skip = 0, limit = 100, category = null, activeOnly = false) => {
    const params = new URLSearchParams({ skip, limit })
    if (category) params.append('category', category)
    if (activeOnly) params.append('active_only', 'true')
    return api.get(`/custom-qa/?${params}`)
  },
  create: (data) => api.post('/custom-qa/', data),
  update: (qaId, data) => api.put(`/custom-qa/${qaId}`, data),
  delete: (qaId) => api.delete(`/custom-qa/${qaId}`),
  toggle: (qaId) => api.patch(`/custom-qa/${qaId}/toggle`),
}

// ── Departments ───────────────────────────
export const departmentsAPI = {
  list: () => api.get('/departments'),
  create: (name) => api.post('/departments', { name }),
  delete: (deptId) => api.delete(`/departments/${deptId}`),
}

export default api
