/**
 * @file CustomQAPage.jsx
 * @description Core React component/service for the Project Nexus application.
 */

import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  HiOutlinePlusCircle,
  HiOutlineTrash,
  HiOutlinePencilSquare,
  HiOutlineCheck,
  HiOutlineXMark,
  HiOutlineChatBubbleLeftRight,
} from 'react-icons/hi2'
import { customQaAPI } from '../services/api'
import PageTransition from '../components/PageTransition'
import toast from 'react-hot-toast'
import './CustomQAPage.css'

export default function CustomQAPage() {
  const [entries, setEntries] = useState([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [editId, setEditId] = useState(null)
  const [form, setForm] = useState({
    question_patterns: [''],
    answer: '',
    category: '',
    priority: 0,
  })

  useEffect(() => {
    loadEntries()
  }, [])

  const loadEntries = async () => {
    try {
      setLoading(true)
      const { data } = await customQaAPI.list()
      if (data.success) {
        setEntries(data.data || [])
      }
    } catch (err) {
      toast.error('Failed to load Q&A entries')
    } finally {
      setLoading(false)
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    const patterns = form.question_patterns.filter((p) => p.trim())
    if (!patterns.length || !form.answer.trim()) {
      toast.error('Patterns and answer are required')
      return
    }

    try {
      const payload = {
        question_patterns: patterns,
        answer: form.answer.trim(),
        category: form.category.trim() || null,
        priority: parseInt(form.priority) || 0,
      }

      if (editId) {
        await customQaAPI.update(editId, payload)
        toast.success('Q&A updated')
      } else {
        await customQaAPI.create(payload)
        toast.success('Q&A created')
      }

      resetForm()
      loadEntries()
    } catch (err) {
      toast.error(err.response?.data?.error?.message || 'Save failed')
    }
  }

  const handleDelete = async (id) => {
    if (!confirm('Delete this Q&A entry?')) return
    try {
      await customQaAPI.delete(id)
      toast.success('Deleted')
      loadEntries()
    } catch {
      toast.error('Delete failed')
    }
  }

  const handleToggle = async (id) => {
    try {
      await customQaAPI.toggle(id)
      loadEntries()
    } catch {
      toast.error('Toggle failed')
    }
  }

  const handleEdit = (entry) => {
    setEditId(entry.id)
    setForm({
      question_patterns: entry.question_patterns || [''],
      answer: entry.answer || '',
      category: entry.category || '',
      priority: entry.priority || 0,
    })
    setShowForm(true)
  }

  const resetForm = () => {
    setEditId(null)
    setShowForm(false)
    setForm({ question_patterns: [''], answer: '', category: '', priority: 0 })
  }

  const addPattern = () => {
    setForm((f) => ({
      ...f,
      question_patterns: [...f.question_patterns, ''],
    }))
  }

  const removePattern = (idx) => {
    setForm((f) => ({
      ...f,
      question_patterns: f.question_patterns.filter((_, i) => i !== idx),
    }))
  }

  const updatePattern = (idx, val) => {
    setForm((f) => {
      const patterns = [...f.question_patterns]
      patterns[idx] = val
      return { ...f, question_patterns: patterns }
    })
  }

  return (
    <PageTransition>
      <div className="cqa-page">
        <div className="cqa-header">
          <div>
            <h1 className="cqa-title">
              <HiOutlineChatBubbleLeftRight /> Custom Q&A
            </h1>
            <p className="cqa-subtitle">
              Define question patterns and answers that bypass the RAG pipeline for instant responses.
            </p>
          </div>
          <motion.button
            className="cqa-add-btn"
            onClick={() => {
              resetForm()
              setShowForm(true)
            }}
            whileHover={{ scale: 1.03 }}
            whileTap={{ scale: 0.97 }}
          >
            <HiOutlinePlusCircle /> Add Entry
          </motion.button>
        </div>

        {/* Form */}
        <AnimatePresence>
          {showForm && (
            <motion.form
              className="cqa-form"
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              onSubmit={handleSubmit}
            >
              <h3 className="cqa-form__title">
                {editId ? 'Edit Q&A' : 'New Q&A'}
              </h3>

              <div className="cqa-form__group">
                <label>Question Patterns</label>
                {form.question_patterns.map((p, i) => (
                  <div key={i} className="cqa-form__pattern-row">
                    <input
                      type="text"
                      value={p}
                      onChange={(e) => updatePattern(i, e.target.value)}
                      placeholder="e.g. What are the holidays?"
                    />
                    {form.question_patterns.length > 1 && (
                      <button
                        type="button"
                        className="cqa-form__remove-btn"
                        onClick={() => removePattern(i)}
                      >
                        <HiOutlineXMark />
                      </button>
                    )}
                  </div>
                ))}
                <button
                  type="button"
                  className="cqa-form__add-pattern"
                  onClick={addPattern}
                >
                  + Add pattern
                </button>
              </div>

              <div className="cqa-form__group">
                <label>Answer</label>
                <textarea
                  value={form.answer}
                  onChange={(e) => setForm((f) => ({ ...f, answer: e.target.value }))}
                  placeholder="The curated answer..."
                  rows={4}
                />
              </div>

              <div className="cqa-form__row">
                <div className="cqa-form__group">
                  <label>Category</label>
                  <input
                    type="text"
                    value={form.category}
                    onChange={(e) => setForm((f) => ({ ...f, category: e.target.value }))}
                    placeholder="e.g. HR, IT, General"
                  />
                </div>
                <div className="cqa-form__group">
                  <label>Priority (0-100)</label>
                  <input
                    type="number"
                    value={form.priority}
                    onChange={(e) => setForm((f) => ({ ...f, priority: e.target.value }))}
                    min={0}
                    max={100}
                  />
                </div>
              </div>

              <div className="cqa-form__actions">
                <button type="button" className="cqa-form__cancel" onClick={resetForm}>
                  Cancel
                </button>
                <button type="submit" className="cqa-form__save">
                  <HiOutlineCheck /> {editId ? 'Update' : 'Create'}
                </button>
              </div>
            </motion.form>
          )}
        </AnimatePresence>

        {/* Entries List */}
        {loading ? (
          <div className="cqa-loading">Loading...</div>
        ) : entries.length === 0 ? (
          <div className="cqa-empty">
            No custom Q&A entries yet. Click "Add Entry" to create one.
          </div>
        ) : (
          <div className="cqa-entries">
            {entries.map((entry) => (
              <motion.div
                key={entry.id}
                className={`cqa-entry ${!entry.is_active ? 'cqa-entry--inactive' : ''}`}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                layout
              >
                <div className="cqa-entry__header">
                  <div className="cqa-entry__meta">
                    {entry.category && (
                      <span className="cqa-entry__category">{entry.category}</span>
                    )}
                    <span className="cqa-entry__priority">Priority: {entry.priority}</span>
                    <span className={`cqa-entry__status ${entry.is_active ? 'active' : 'inactive'}`}>
                      {entry.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </div>
                  <div className="cqa-entry__actions">
                    <button onClick={() => handleToggle(entry.id)} title="Toggle active">
                      {entry.is_active ? '⏸' : '▶'}
                    </button>
                    <button onClick={() => handleEdit(entry)} title="Edit">
                      <HiOutlinePencilSquare />
                    </button>
                    <button onClick={() => handleDelete(entry.id)} title="Delete" className="danger">
                      <HiOutlineTrash />
                    </button>
                  </div>
                </div>

                <div className="cqa-entry__patterns">
                  <strong>Patterns:</strong>
                  <div className="cqa-entry__pattern-tags">
                    {(entry.question_patterns || []).map((p, i) => (
                      <span key={i} className="cqa-entry__pattern-tag">"{p}"</span>
                    ))}
                  </div>
                </div>

                <div className="cqa-entry__answer">
                  <strong>Answer:</strong>
                  <p>{entry.answer}</p>
                </div>
              </motion.div>
            ))}
          </div>
        )}
      </div>
    </PageTransition>
  )
}
