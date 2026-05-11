/**
 * @file DocumentsPage.jsx
 * @description Core React component/service for the Project Nexus application.
 */

import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  HiOutlineRectangleStack,
  HiOutlineTrash,
  HiOutlineFunnel,
  HiOutlineMagnifyingGlass,
} from 'react-icons/hi2'
import { docsAPI, queryDebugAPI } from '../services/api'
import { useAuth } from '../context/AuthContext'
import PageTransition from '../components/PageTransition'
import toast from 'react-hot-toast'
import './DocumentsPage.css'

const STATUS_COLORS = {
  completed: 'var(--accent)',
  processing: 'var(--warning)',
  failed: 'var(--danger)',
}

export default function DocumentsPage() {
  const { isAdmin } = useAuth()
  const [docs, setDocs] = useState([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('')
  const [clearing, setClearing] = useState(false)
  const [deleteUploads, setDeleteUploads] = useState(false)
  const [pruning, setPruning] = useState(false)
  const [debugQuery, setDebugQuery] = useState('')
  const [debugDoc, setDebugDoc] = useState('')
  const [debugLoading, setDebugLoading] = useState(false)
  const [debugResult, setDebugResult] = useState(null)

  const fetchDocs = async () => {
    setLoading(true)
    try {
      const { data } = await docsAPI.list(0, 1000)
      if (data.success) setDocs(data.data || [])
    } catch (err) {
      setDocs([])
      toast.error('Failed to load documents')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchDocs() }, [])

  const handleDelete = async (id, name) => {
    try {
      const { data } = await docsAPI.delete(id)
      if (data.success) {
        toast.success('Document deleted')
        setDocs((prev) => prev.filter((d) => d.id !== id))
      }
    } catch (err) {
      const code = err.response?.data?.error?.code
      if (code === 'RECORD_NOT_FOUND') {
        toast.error('Document already removed. Refreshing list...')
        fetchDocs()
        return
      }
      toast.error(err.response?.data?.error?.message || 'Delete failed')
    }
  }

  const handleClearAll = async () => {
    if (docs.length === 0) {
      toast('No documents to clear')
      return
    }

    const warning = deleteUploads
      ? 'This will delete ALL documents, chunks, and uploaded files. This cannot be undone.'
      : 'This will delete ALL documents and chunks. Uploaded files will be kept. This cannot be undone.'

    if (!window.confirm(warning)) {
      return
    }

    setClearing(true)
    try {
      const { data } = await docsAPI.clearAll(deleteUploads)
      if (data.success) {
        const deleted = data.data?.deleted_documents ?? 0
        const remaining = data.data?.remaining_documents ?? 0
        setDocs([])
        toast.success(`Cleared ${deleted} documents (remaining: ${remaining})`)
        await fetchDocs()
      } else {
        toast.error(data.error?.message || 'Clear all failed')
      }
    } catch (err) {
      toast.error(err.response?.data?.error?.message || 'Clear all failed')
    } finally {
      setClearing(false)
    }
  }

  const handlePruneMissing = async () => {
    if (!window.confirm('Remove documents missing on disk? This will also remove their vectors.')) {
      return
    }

    setPruning(true)
    try {
      const { data } = await docsAPI.pruneMissing()
      if (data.success) {
        const pruned = data.data?.pruned_documents ?? 0
        const failed = data.data?.failed_documents ?? 0
        const message = failed > 0
          ? `Pruned ${pruned} documents (${failed} failed)`
          : `Pruned ${pruned} documents`
        toast.success(message)
        await fetchDocs()
      } else {
        toast.error(data.error?.message || 'Prune failed')
      }
    } catch (err) {
      toast.error(err.response?.data?.error?.message || 'Prune failed')
    } finally {
      setPruning(false)
    }
  }

  const filtered = docs.filter((d) =>
    !filter || d.filename?.toLowerCase().includes(filter.toLowerCase()) ||
    d.department?.toLowerCase().includes(filter.toLowerCase())
  )

  const formatBytes = (b) => {
    if (!b) return '—'
    if (b < 1024) return b + ' B'
    if (b < 1024 * 1024) return (b / 1024).toFixed(1) + ' KB'
    return (b / (1024 * 1024)).toFixed(1) + ' MB'
  }

  const handleDebugContains = async () => {
    if (!debugQuery.trim()) {
      toast.error('Enter a search phrase')
      return
    }

    setDebugLoading(true)
    try {
      const { data } = await queryDebugAPI.contains(
        debugQuery.trim(),
        debugDoc || null,
        null,
        200
      )

      if (data.success) {
        setDebugResult(data.data)
        toast.success(`Found ${data.data.match_count} matching chunks`)
      } else {
        setDebugResult(null)
        toast.error(data.error?.message || 'Debug check failed')
      }
    } catch (err) {
      setDebugResult(null)
      toast.error(err.response?.data?.error?.message || 'Debug check failed')
    } finally {
      setDebugLoading(false)
    }
  }

  return (
    <PageTransition>
      <div className="docs-page">
        <motion.div
          className="page-header"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
        >
          <div className="page-header__row">
            <div>
              <h1 className="page-title">
                <HiOutlineRectangleStack style={{ verticalAlign: 'middle' }} /> Documents
              </h1>
              <p className="page-subtitle">{docs.length} documents in knowledge base</p>
            </div>
            {isAdmin && (
              <div className="docs-actions">
                <label className="docs-actions__toggle">
                  <input
                    type="checkbox"
                    checked={deleteUploads}
                    onChange={(e) => setDeleteUploads(e.target.checked)}
                  />
                  <span>Delete uploaded files</span>
                </label>
                <button
                  type="button"
                  className="docs-clear"
                  onClick={handleClearAll}
                  disabled={clearing}
                >
                  {clearing ? 'Clearing...' : 'Clear All'}
                </button>
                <button
                  type="button"
                  className="docs-clear"
                  onClick={handlePruneMissing}
                  disabled={pruning}
                >
                  {pruning ? 'Pruning...' : 'Cleanup Missing'}
                </button>
              </div>
            )}
          </div>
        </motion.div>

        {isAdmin && (
          <motion.div
            className="docs-debug"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
          >
            <div className="docs-debug__header">
              <HiOutlineMagnifyingGlass />
              <span>Chunk Debug</span>
            </div>
            <div className="docs-debug__controls">
              <input
                className="docs-debug__input"
                value={debugQuery}
                onChange={(e) => setDebugQuery(e.target.value)}
                placeholder="Search text in stored chunks"
              />
              <select
                className="docs-debug__select"
                value={debugDoc}
                onChange={(e) => setDebugDoc(e.target.value)}
              >
                <option value="">All documents</option>
                {docs.map((doc) => (
                  <option key={doc.id} value={doc.id}>
                    {doc.filename}
                  </option>
                ))}
              </select>
              <button
                type="button"
                className="docs-clear"
                onClick={handleDebugContains}
                disabled={debugLoading}
              >
                {debugLoading ? 'Checking...' : 'Check Chunks'}
              </button>
            </div>
            {debugResult && (
              <div className="docs-debug__result">
                <div className="docs-debug__summary">
                  <span><strong>{debugResult.match_count}</strong> matches</span>
                  <span><strong>{debugResult.total_chunks}</strong> total chunks</span>
                </div>
                {debugResult.matches?.length > 0 ? (
                  <div className="docs-debug__matches">
                    {debugResult.matches.slice(0, 5).map((match, idx) => (
                      <div key={idx} className="docs-debug__match">
                        <div className="docs-debug__match-head">
                          <span>Chunk {match.chunk_index}</span>
                        </div>
                        <p>{match.preview}</p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="docs-debug__empty">No chunks contain that phrase.</p>
                )}
              </div>
            )}
          </motion.div>
        )}

        {/* Filter */}
        <motion.div
          className="docs-filter"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15 }}
        >
          <HiOutlineFunnel className="docs-filter__icon" />
          <input
            className="docs-filter__input"
            placeholder="Filter by name or department..."
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          />
        </motion.div>

        {/* Table */}
        {loading ? (
          <div className="docs-loading">
            {[...Array(5)].map((_, i) => (
              <motion.div
                key={i}
                className="docs-skeleton"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: i * 0.08 }}
              />
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <motion.div
            className="docs-empty"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
          >
            <p>No documents found</p>
          </motion.div>
        ) : (
          <div className="docs-grid">
            <AnimatePresence>
              {filtered.map((doc, i) => (
                <motion.div
                  key={doc.id}
                  className="docs-card"
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, scale: 0.95 }}
                  transition={{ delay: i * 0.04, duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
                  whileHover={{ y: -4, transition: { duration: 0.2 } }}
                  layout
                >
                  <div className="docs-card__header">
                    <span
                      className="docs-card__status"
                      style={{ background: STATUS_COLORS[doc.status] || 'var(--text-tertiary)' }}
                    />
                    <span className="docs-card__type">{doc.file_type?.toUpperCase()}</span>
                    {isAdmin && (
                      <button
                        className="docs-card__delete"
                        type="button"
                        onClick={() => handleDelete(doc.id, doc.filename)}
                        title="Delete"
                      >
                        <HiOutlineTrash />
                      </button>
                    )}
                  </div>
                  <h3 className="docs-card__name">{doc.filename}</h3>
                  <div className="docs-card__meta">
                    <span>{formatBytes(doc.file_size_bytes)}</span>
                    {doc.total_chunks != null && <span>{doc.total_chunks} chunks</span>}
                    {doc.hierarchy != null && <span>Level {doc.hierarchy}</span>}
                    {doc.department && <span className="docs-card__dept">{doc.department}</span>}
                  </div>
                  <div className="docs-card__roles">
                    {doc.allowed_roles?.map((r) => (
                      <span key={r} className="docs-card__role">{r}</span>
                    ))}
                  </div>
                  <div className="docs-card__date">
                    {doc.uploaded_at ? new Date(doc.uploaded_at).toLocaleDateString() : '—'}
                  </div>
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
        )}
      </div>
    </PageTransition>
  )
}
