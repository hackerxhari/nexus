/**
 * @file UsersPage.jsx
 * @description Core React component/service for the Project Nexus application.
 */

import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  HiOutlineUsers,
  HiOutlineUserPlus,
  HiOutlineXMark,
  HiOutlineNoSymbol,
} from 'react-icons/hi2'
import { adminAPI, departmentsAPI } from '../services/api'
import { useAuth } from '../context/AuthContext'
import PageTransition from '../components/PageTransition'
import toast from 'react-hot-toast'
import './UsersPage.css'

export default function UsersPage() {
  const { user: currentUser } = useAuth()
  const [users, setUsers] = useState([])
  const [departments, setDepartments] = useState([])
  const [loading, setLoading] = useState(true)
  const [showModal, setShowModal] = useState(false)
  const ROLE_OPTIONS = currentUser?.roles?.includes('admin')
    ? ['ceo', 'manager', 'employee']
    : currentUser?.roles?.includes('ceo')
      ? ['manager', 'employee']
      : currentUser?.roles?.includes('manager')
        ? ['employee']
        : []

  const [form, setForm] = useState({
    email: '', full_name: '', password: '', roles: [], department: ''
  })
  const [creating, setCreating] = useState(false)

  const fetchData = async () => {
    setLoading(true)
    try {
      const [usersRes, deptsRes] = await Promise.all([
        adminAPI.listUsers(0, 100),
        departmentsAPI.list()
      ])
      if (usersRes.data.success) setUsers(usersRes.data.data || [])
      if (deptsRes.data.success) setDepartments(deptsRes.data.data || [])
    } catch {
      toast.error('Failed to load data')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchData() }, [])

  const handleCreate = async () => {
    if (!form.email || !form.full_name || !form.password || form.roles.length === 0) {
      toast.error('Fill all required fields')
      return
    }
    setCreating(true)
    try {
      const { data } = await adminAPI.createUser({
        email: form.email,
        full_name: form.full_name,
        password: form.password,
        roles: form.roles,
        department: form.department || null
      })
      if (data.success) {
        toast.success('User created!')
        setShowModal(false)
        setForm({ email: '', full_name: '', password: '', roles: [], department: '' })
        fetchData()
      } else {
        toast.error(data.error?.message || 'Failed')
      }
    } catch (err) {
      const detail = err.response?.data?.detail
      if (Array.isArray(detail) && detail.length > 0) {
        toast.error(`Validation Error: ${detail[0].msg}`)
      } else {
        toast.error(err.response?.data?.error?.message || 'Failed')
      }
    } finally {
      setCreating(false)
    }
  }

  const handleDeactivate = async (userId, email) => {
    if (!confirm(`Deactivate "${email}"?`)) return
    try {
      const { data } = await adminAPI.deactivateUser(userId)
      if (data.success) {
        toast.success('User deactivated')
        fetchData()
      } else {
        toast.error(data.error?.message || 'Failed to deactivate')
      }
    } catch (err) {
      toast.error(err.response?.data?.error?.message || 'Failed to deactivate')
    }
  }

  const handleDelete = async (userId, email) => {
    if (!confirm(`Delete user "${email}" permanently?`)) return
    try {
      const { data } = await adminAPI.deleteUser(userId)
      if (data.success) {
        toast.success('User deleted')
        fetchData()
      } else {
        toast.error(data.error?.message || 'Failed to delete')
      }
    } catch (err) {
      toast.error(err.response?.data?.error?.message || 'Failed to delete')
    }
  }

  const toggleFormRole = (role) => {
    setForm((prev) => ({
      ...prev,
      roles: prev.roles.includes(role)
        ? prev.roles.filter((r) => r !== role)
        : [...prev.roles, role],
    }))
  }

  return (
    <PageTransition>
      <div className="users-page">
        <motion.div
          className="page-header"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <div className="page-header__row">
            <div>
              <h1 className="page-title">
                <HiOutlineUsers style={{ verticalAlign: 'middle' }} /> Users
              </h1>
              <p className="page-subtitle">{users.length} registered users</p>
            </div>
            <motion.button
              className="btn btn--primary"
              onClick={() => setShowModal(true)}
              whileHover={{ scale: 1.03 }}
              whileTap={{ scale: 0.97 }}
            >
              <HiOutlineUserPlus /> Add User
            </motion.button>
          </div>
        </motion.div>

        {/* User table */}
        <div className="users-table-wrap">
          <table className="users-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Email</th>
                <th>Roles</th>
                <th>Department</th>
                <th>Hierarchy</th>
                <th>Status</th>
                <th>Last Login</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <AnimatePresence>
                {users.map((u, i) => (
                  <motion.tr
                    key={u.id}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.03, duration: 0.3 }}
                  >
                    <td className="users-table__name">
                      <div className="users-table__avatar">
                        {u.full_name?.charAt(0) || '?'}
                      </div>
                      {u.full_name}
                    </td>
                    <td className="users-table__email">{u.email}</td>
                    <td>
                      <div className="users-table__roles">
                        {u.roles?.map((r) => (
                          <span key={r} className="users-table__role">{r}</span>
                        ))}
                      </div>
                    </td>
                    <td className="users-table__dept">{u.department || '—'}</td>
                    <td className="users-table__hierarchy">{u.hierarchy}</td>
                    <td>
                      <span className={`users-table__status ${u.is_active ? 'users-table__status--active' : 'users-table__status--inactive'}`}>
                        {u.is_active ? 'Active' : 'Disabled'}
                      </span>
                    </td>
                    <td className="users-table__date">
                      {u.last_login_at ? new Date(u.last_login_at).toLocaleDateString() : 'Never'}
                    </td>
                    <td>
                      {u.is_active && (
                        <button
                          className="users-table__action"
                          onClick={() => handleDeactivate(u.id, u.email)}
                          title="Deactivate"
                        >
                          <HiOutlineNoSymbol />
                        </button>
                      )}
                      {(currentUser?.roles?.includes('superadmin') || u.hierarchy < currentUser?.hierarchy) && !u.roles?.includes('superadmin') && (
                        <button
                          className="users-table__action"
                          onClick={() => handleDelete(u.id, u.email)}
                          title="Delete"
                          style={{ color: 'var(--danger)' }}
                        >
                          <HiOutlineXMark />
                        </button>
                      )}
                    </td>
                  </motion.tr>
                ))}
              </AnimatePresence>
            </tbody>
          </table>
        </div>

        {/* Create User Modal */}
        <AnimatePresence>
          {showModal && (
            <motion.div
              className="modal-overlay"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setShowModal(false)}
            >
              <motion.div
                className="modal"
                initial={{ opacity: 0, scale: 0.9, y: 40 }}
                animate={{ opacity: 1, scale: 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.9, y: 40 }}
                transition={{ type: 'spring', stiffness: 400, damping: 30 }}
                onClick={(e) => e.stopPropagation()}
              >
                <div className="modal__header">
                  <h2 className="modal__title">Create User</h2>
                  <button className="modal__close" onClick={() => setShowModal(false)}>
                    <HiOutlineXMark />
                  </button>
                </div>

                <div className="modal__body">
                  <div className="form-field">
                    <label className="form-field__label">Full Name *</label>
                    <input
                      className="form-input"
                      value={form.full_name}
                      onChange={(e) => setForm({ ...form, full_name: e.target.value })}
                      placeholder="John Doe"
                    />
                  </div>
                  <div className="form-field">
                    <label className="form-field__label">Email *</label>
                    <input
                      className="form-input"
                      type="email"
                      value={form.email}
                      onChange={(e) => setForm({ ...form, email: e.target.value })}
                      placeholder="john@company.com"
                    />
                  </div>
                  <div className="form-field">
                    <label className="form-field__label">Password *</label>
                    <input
                      className="form-input"
                      type="password"
                      value={form.password}
                      onChange={(e) => setForm({ ...form, password: e.target.value })}
                      placeholder="Min 8 chars, 1 uppercase, 1 number"
                    />
                  </div>
                  <div className="form-field">
                    <label className="form-field__label">Roles *</label>
                    <div className="form-roles">
                      {ROLE_OPTIONS.map((role) => (
                        <motion.button
                          key={role}
                          className={`form-role-chip ${form.roles.includes(role) ? 'form-role-chip--active' : ''}`}
                          onClick={() => toggleFormRole(role)}
                          whileHover={{ scale: 1.05 }}
                          whileTap={{ scale: 0.95 }}
                        >
                          {role}
                        </motion.button>
                      ))}
                    </div>
                  </div>

                  <div className="form-field">
                    <label className="form-field__label">Department</label>
                    <select
                      className="form-input"
                      value={form.department}
                      onChange={(e) => setForm({ ...form, department: e.target.value })}
                    >
                      <option value="">-- No Department --</option>
                      {departments.map((d) => (
                        <option key={d.id} value={d.name}>{d.name}</option>
                      ))}
                    </select>
                  </div>
                </div>

                <div className="modal__footer">
                  <button className="btn btn--outline" onClick={() => setShowModal(false)}>Cancel</button>
                  <motion.button
                    className="btn btn--primary"
                    onClick={handleCreate}
                    disabled={creating}
                    whileHover={{ scale: 1.03 }}
                    whileTap={{ scale: 0.97 }}
                  >
                    {creating ? 'Creating...' : 'Create User'}
                  </motion.button>
                </div>
              </motion.div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </PageTransition>
  )
}
