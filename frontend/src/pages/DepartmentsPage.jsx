/**
 * @file DepartmentsPage.jsx
 * @description Core React component/service for the Project Nexus application.
 */

import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  HiOutlineBuildingOffice2,
  HiOutlinePlus,
  HiOutlineXMark,
  HiOutlineTrash,
} from 'react-icons/hi2'
import { departmentsAPI, adminAPI } from '../services/api'
import { useAuth } from '../context/AuthContext'
import PageTransition from '../components/PageTransition'
import toast from 'react-hot-toast'
import './DepartmentsPage.css'

export default function DepartmentsPage() {
  const { user: currentUser } = useAuth()
  const [departments, setDepartments] = useState([])
  const [loading, setLoading] = useState(true)
  const [showModal, setShowModal] = useState(false)
  const [form, setForm] = useState({ name: '' })
  const [creating, setCreating] = useState(false)

  const fetchData = async () => {
    setLoading(true)
    try {
      const [deptRes] = await Promise.all([
        departmentsAPI.list(),
      ])
      if (deptRes.data.success) setDepartments(deptRes.data.data || [])
    } catch {
      toast.error('Failed to load data')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchData() }, [])

  const handleCreate = async () => {
    if (!form.name) {
      toast.error('Name is required')
      return
    }
    setCreating(true)
    try {
      const { data } = await departmentsAPI.create(form.name)
      if (data.success) {
        toast.success('Department created!')
        setShowModal(false)
        setForm({ name: '' })
        fetchData()
      } else {
        toast.error(data.error?.message || 'Failed')
      }
    } catch (err) {
      toast.error(err.response?.data?.error?.message || 'Failed')
    } finally {
      setCreating(false)
    }
  }

  const handleDelete = async (deptId, name) => {
    if (!window.confirm(`Delete department "${name}"?`)) return
    try {
      const { data } = await departmentsAPI.delete(deptId)
      if (data.success) {
        toast.success('Department deleted')
        fetchData()
      }
    } catch {
      toast.error('Failed to delete')
    }
  }

  return (
    <PageTransition>
      <div className="departments-page">
        <motion.div
          className="page-header"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <div className="page-header__row">
            <div>
              <h1 className="page-title">
                <HiOutlineBuildingOffice2 style={{ verticalAlign: 'middle' }} /> Departments
              </h1>
              <p className="page-subtitle">{departments.length} departments found</p>
            </div>
            {(currentUser?.roles?.includes('admin') || currentUser?.roles?.includes('ceo')) && (
              <motion.button
                className="btn btn--primary"
                onClick={() => setShowModal(true)}
                whileHover={{ scale: 1.03 }}
                whileTap={{ scale: 0.97 }}
              >
                <HiOutlinePlus /> Add Department
              </motion.button>
            )}
          </div>
        </motion.div>

        <div className="departments-table-wrap">
          <table className="departments-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Name</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              <AnimatePresence>
                {departments.map((d, i) => (
                  <motion.tr
                    key={d.id}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.03, duration: 0.3 }}
                  >
                    <td>{d.id}</td>
                    <td className="departments-table__name">{d.name}</td>
                    <td>
                      {(currentUser?.roles?.includes('admin') || currentUser?.roles?.includes('ceo')) && (
                        <button
                          className="departments-table__action"
                          onClick={() => handleDelete(d.id, d.name)}
                          title="Delete"
                        >
                          <HiOutlineTrash />
                        </button>
                      )}
                    </td>
                  </motion.tr>
                ))}
              </AnimatePresence>
            </tbody>
          </table>
        </div>

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
                  <h2 className="modal__title">Create Department</h2>
                  <button className="modal__close" onClick={() => setShowModal(false)}>
                    <HiOutlineXMark />
                  </button>
                </div>

                <div className="modal__body">
                  <div className="form-field">
                    <label className="form-field__label">Department Name *</label>
                    <input
                      className="form-input"
                      value={form.name}
                      onChange={(e) => setForm({ ...form, name: e.target.value })}
                      placeholder="e.g. Engineering"
                    />
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
                    {creating ? 'Creating...' : 'Create'}
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
