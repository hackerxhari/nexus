/**
 * @file UploadPage.jsx
 * @description Core React component/service for the Project Nexus application.
 */

import { useState, useCallback, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useDropzone } from 'react-dropzone'
import {
  HiOutlineCloudArrowUp,
  HiOutlineDocumentText,
  HiOutlineXMark,
  HiOutlineCheck,
  HiOutlineArrowPath,
} from 'react-icons/hi2'
import { docsAPI, departmentsAPI } from '../services/api'
import { useAuth } from '../context/AuthContext'
import PageTransition from '../components/PageTransition'
import toast from 'react-hot-toast'
import './UploadPage.css'

const ROLE_OPTIONS = ['admin', 'ceo', 'manager', 'employee']

export default function UploadPage() {
  const { user: currentUser } = useAuth()
  const [files, setFiles] = useState([])
  const [roles, setRoles] = useState([])
  const [departments, setDepartments] = useState([])
  const [selectedDepartments, setSelectedDepartments] = useState([])

  const [hierarchy, setHierarchy] = useState(1)
  const [documentName, setDocumentName] = useState('')
  const [uploading, setUploading] = useState(false)
  const [result, setResult] = useState(null)
  const [uploadProgress, setUploadProgress] = useState(null)

  useEffect(() => {
    departmentsAPI.list().then(res => {
      if (res.data.success) setDepartments(res.data.data)
    })
  }, [])

  const onDrop = useCallback((accepted) => {
    if (accepted.length > 0) {
      setFiles((prev) => {
        const next = [...prev]
        accepted.forEach((incoming) => {
          const exists = next.some(
            (current) =>
              current.name === incoming.name
              && current.size === incoming.size
              && current.lastModified === incoming.lastModified
          )
          if (!exists) {
            next.push(incoming)
          }
        })
        return next
      })
      setResult(null)
    }
  }, [])

  const onDropRejected = useCallback((rejections) => {
    if (rejections.length === 0) {
      return
    }

    const rejectedNames = rejections
      .map((item) => item.file?.name)
      .filter(Boolean)

    if (rejectedNames.length > 0) {
      toast.error(`Rejected files: ${rejectedNames.join(', ')}`)
    } else {
      toast.error('Some files were rejected. Check file types and size limits.')
    }
  }, [])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    onDropRejected,
    multiple: true,
    accept: {
      'application/pdf': ['.pdf'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
      'text/plain': ['.txt'],
      'image/png': ['.png'],
      'image/jpeg': ['.jpg', '.jpeg'],
    },
  })

  const toggleRole = (role) => {
    setRoles((prev) =>
      prev.includes(role) ? prev.filter((r) => r !== role) : [...prev, role]
    )
  }

  const handleUpload = async () => {
    if (files.length === 0 || roles.length === 0) {
      toast.error('Select one or more files and at least one role')
      return
    }

    setUploading(true)
    setUploadProgress({
      total: files.length,
      processed: 0,
      uploaded: 0,
      failed: 0,
      current: '',
    })
    try {
      const uploaded = []
      const failed = []
      const roleString = roles.join(',')

      for (let index = 0; index < files.length; index += 1) {
        const currentFile = files[index]
        setUploadProgress((prev) => ({
          ...prev,
          current: currentFile.name,
        }))

        try {
          const { data } = await docsAPI.upload(
            currentFile,
            roleString,
            selectedDepartments.join(',') || undefined,
            documentName || undefined
          )

          if (data.success) {
            uploaded.push(data.data)
            setUploadProgress((prev) => ({
              ...prev,
              processed: index + 1,
              uploaded: prev.uploaded + 1,
            }))
          } else {
            failed.push({
              file: currentFile,
              filename: currentFile.name,
              message: data.error?.message || 'Upload failed',
            })
            setUploadProgress((prev) => ({
              ...prev,
              processed: index + 1,
              failed: prev.failed + 1,
            }))
          }
        } catch (err) {
          failed.push({
            file: currentFile,
            filename: currentFile.name,
            message: err.response?.data?.error?.message || 'Upload failed',
          })
          setUploadProgress((prev) => ({
            ...prev,
            processed: index + 1,
            failed: prev.failed + 1,
          }))
        }
      }

      const totalChunks = uploaded.reduce((sum, item) => sum + (item.total_chunks || 0), 0)
      const totalWords = uploaded.reduce((sum, item) => sum + (item.total_words || 0), 0)
      const totalIngestionTime = uploaded.reduce(
        (sum, item) => sum + (item.ingestion_time_seconds || 0),
        0
      )

      setResult({
        uploaded_count: uploaded.length,
        failed_count: failed.length,
        total_chunks: totalChunks,
        total_words: totalWords,
        ingestion_time_seconds: totalIngestionTime,
        filenames: uploaded.map((item) => item.filename),
        failures: failed,
      })

      if (uploaded.length > 0) {
        setFiles([])
        if (failed.length > 0) {
          toast.error(`Uploaded ${uploaded.length}, failed ${failed.length}`)
        } else {
          toast.success(`Ingested ${uploaded.length} files (${totalChunks} chunks)!`)
        }
      } else {
        toast.error('All uploads failed. Fix and retry failed files.')
      }
    } finally {
      setUploading(false)
      setUploadProgress(null)
    }
  }

  const handleRetryFailure = async (failedIndex) => {
    if (!result || !result.failures?.[failedIndex]) {
      return
    }

    const targetFailure = result.failures[failedIndex]
    const targetFile = targetFailure.file
    if (!targetFile) {
      toast.error('Retry data unavailable for this file')
      return
    }

    try {
      setUploading(true)
      const { data } = await docsAPI.upload(
        targetFile,
        roles.join(','),
        selectedDepartments.join(',') || undefined,
        parseInt(hierarchy, 10),
        documentName || undefined
      )

      if (!data.success) {
        toast.error(data.error?.message || `Retry failed for ${targetFailure.filename}`)
        return
      }

      setResult((prev) => {
        if (!prev) return prev

        const nextFailures = prev.failures.filter((_, idx) => idx !== failedIndex)
        return {
          ...prev,
          uploaded_count: prev.uploaded_count + 1,
          failed_count: Math.max(0, prev.failed_count - 1),
          total_chunks: prev.total_chunks + (data.data.total_chunks || 0),
          total_words: prev.total_words + (data.data.total_words || 0),
          ingestion_time_seconds: prev.ingestion_time_seconds + (data.data.ingestion_time_seconds || 0),
          filenames: [...prev.filenames, data.data.filename],
          failures: nextFailures,
        }
      })

      toast.success(`Retried ${targetFailure.filename} successfully`)
    } catch (err) {
      toast.error(err.response?.data?.error?.message || `Retry failed for ${targetFailure.filename}`)
    } finally {
      setUploading(false)
    }
  }

  const resetForm = () => {
    setFiles([])
    setRoles([])
    setSelectedDepartments([])
    setHierarchy(1)
    setDocumentName('')
    setResult(null)
    setUploadProgress(null)
  }

  const removeFileAt = (indexToRemove) => {
    setFiles((prev) => prev.filter((_, index) => index !== indexToRemove))
  }

  const formatBytes = (bytes) => {
    if (bytes < 1024) return bytes + ' B'
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
  }

  return (
    <PageTransition>
      <div className="upload-page">
        <motion.div
          className="page-header"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
        >
          <h1 className="page-title">Upload Documents</h1>
          <p className="page-subtitle">
            Ingest one or more documents into the knowledge base. Supported: PDF, DOCX, TXT, Images
          </p>
        </motion.div>

        <AnimatePresence mode="wait">
          {result ? (
            <motion.div
              key="result"
              className="upload-result"
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
            >
              <div className="upload-result__icon">
                <HiOutlineCheck />
              </div>
              <h2 className="upload-result__title">Ingestion Complete</h2>
              <div className="upload-result__grid">
                <div className="upload-result__stat">
                  <span className="upload-result__stat-value">{result.uploaded_count}</span>
                  <span className="upload-result__stat-label">Uploaded</span>
                </div>
                <div className="upload-result__stat">
                  <span className="upload-result__stat-value">{result.failed_count}</span>
                  <span className="upload-result__stat-label">Failed</span>
                </div>
                <div className="upload-result__stat">
                  <span className="upload-result__stat-value">{result.total_chunks}</span>
                  <span className="upload-result__stat-label">Chunks</span>
                </div>
                <div className="upload-result__stat">
                  <span className="upload-result__stat-value">{result.total_words?.toLocaleString()}</span>
                  <span className="upload-result__stat-label">Words</span>
                </div>
                <div className="upload-result__stat">
                  <span className="upload-result__stat-value">{result.ingestion_time_seconds?.toFixed(1)}s</span>
                  <span className="upload-result__stat-label">Duration</span>
                </div>
              </div>
              <p className="upload-result__filename">
                {result.filenames?.length > 0
                  ? `${result.filenames.length} file(s): ${result.filenames.join(', ')}`
                  : 'No files uploaded'}
              </p>
              {result.failures?.length > 0 && (
                <div className="upload-result__warnings">
                  {result.failures.map((failure, i) => (
                    <div key={i} className="upload-result__warning-row">
                      <span className="upload-result__warning">
                        {failure.filename}: {failure.message}
                      </span>
                      <button
                        type="button"
                        className="btn btn--outline btn--sm"
                        disabled={uploading}
                        onClick={() => handleRetryFailure(i)}
                      >
                        Retry
                      </button>
                    </div>
                  ))}
                </div>
              )}
              <motion.button
                className="btn btn--primary"
                onClick={resetForm}
                whileHover={{ scale: 1.03 }}
                whileTap={{ scale: 0.97 }}
              >
                <HiOutlineArrowPath /> Upload Another
              </motion.button>
            </motion.div>
          ) : (
            <motion.div
              key="form"
              className="upload-form"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              transition={{ duration: 0.5, delay: 0.1 }}
            >
              {/* Drop Zone */}
              <div
                {...getRootProps()}
                className={`upload-dropzone ${isDragActive ? 'upload-dropzone--active' : ''} ${files.length > 0 ? 'upload-dropzone--has-file' : ''}`}
              >
                <input {...getInputProps()} />
                <AnimatePresence mode="wait">
                  {files.length > 0 ? (
                    <motion.div
                      key="files"
                      className="upload-dropzone__file"
                      initial={{ opacity: 0, scale: 0.9 }}
                      animate={{ opacity: 1, scale: 1 }}
                      exit={{ opacity: 0, scale: 0.9 }}
                    >
                      <span className="upload-dropzone__file-count">{files.length} selected</span>
                      <div className="upload-dropzone__file-list">
                        {files.map((currentFile, index) => (
                          <div key={`${currentFile.name}-${currentFile.size}-${currentFile.lastModified}`} className="upload-dropzone__file-item">
                            <HiOutlineDocumentText className="upload-dropzone__file-icon" />
                            <div className="upload-dropzone__file-info">
                              <span className="upload-dropzone__file-name">{currentFile.name}</span>
                              <span className="upload-dropzone__file-size">{formatBytes(currentFile.size)}</span>
                            </div>
                            <button
                              className="upload-dropzone__remove"
                              onClick={(e) => {
                                e.stopPropagation()
                                removeFileAt(index)
                              }}
                            >
                              <HiOutlineXMark />
                            </button>
                          </div>
                        ))}
                      </div>
                    </motion.div>
                  ) : (
                    <motion.div
                      key="empty"
                      className="upload-dropzone__empty"
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      exit={{ opacity: 0 }}
                    >
                      <motion.div
                        animate={{ y: [0, -8, 0] }}
                        transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
                      >
                        <HiOutlineCloudArrowUp className="upload-dropzone__icon" />
                      </motion.div>
                      <p className="upload-dropzone__text">
                        {isDragActive ? 'Drop files here!' : 'Drag & drop files or click to browse'}
                      </p>
                      <p className="upload-dropzone__hint">PDF, DOCX, TXT, PNG, JPG up to 50MB each</p>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>

              {/* Roles */}
              <div className="upload-field">
                <label className="upload-field__label">Access Hierarchy *</label>
                <div className="upload-roles">
                  {ROLE_OPTIONS.map((role) => (
                    <motion.button
                      key={role}
                      className={`upload-role-chip ${roles.includes(role) ? 'upload-role-chip--active' : ''}`}
                      type="button"
                      onClick={() => toggleRole(role)}
                      whileHover={{ scale: 1.05 }}
                      whileTap={{ scale: 0.95 }}
                    >
                      {role}
                    </motion.button>
                  ))}
                </div>
              </div>

              <div className="upload-field">
                <label className="upload-field__label">Document Name</label>
                <input
                  className="upload-input"
                  type="text"
                  value={documentName}
                  onChange={(e) => setDocumentName(e.target.value)}
                  placeholder="Optional custom document name"
                />
              </div>



              <div className="upload-field">
                <label className="upload-field__label">Departments *</label>
                <div className="upload-roles">
                  {departments.map(d => (
                    <motion.button
                      key={d.id}
                      className={`upload-role-chip ${selectedDepartments.includes(d.name) ? 'upload-role-chip--active' : ''}`}
                      type="button"
                      onClick={() => {
                        setSelectedDepartments((prev) =>
                          prev.includes(d.name) ? prev.filter((name) => name !== d.name) : [...prev, d.name]
                        )
                      }}
                      whileHover={{ scale: 1.05 }}
                      whileTap={{ scale: 0.95 }}
                    >
                      {d.name}
                    </motion.button>
                  ))}
                </div>
              </div>

              {/* Upload button */}
              {uploadProgress && (
                <div className="upload-progress">
                  <div className="upload-progress__meta">
                    <span>
                      {uploadProgress.processed} / {uploadProgress.total} processed
                    </span>
                    <span>
                      {uploadProgress.uploaded} succeeded, {uploadProgress.failed} failed
                    </span>
                  </div>
                  {uploadProgress.current && (
                    <p className="upload-progress__current">Uploading: {uploadProgress.current}</p>
                  )}
                  <div className="upload-progress__track">
                    <motion.div
                      className="upload-progress__bar"
                      initial={{ width: 0 }}
                      animate={{ width: `${(uploadProgress.processed / uploadProgress.total) * 100}%` }}
                      transition={{ duration: 0.2, ease: 'easeOut' }}
                    />
                  </div>
                </div>
              )}

              <motion.button
                className="btn btn--primary btn--lg"
                onClick={handleUpload}
                disabled={files.length === 0 || roles.length === 0 || uploading}
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
              >
                {uploading ? (
                  <>
                    <motion.div
                      className="btn-spinner"
                      animate={{ rotate: 360 }}
                      transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
                    />
                    Processing...
                  </>
                ) : (
                  <>
                    <HiOutlineCloudArrowUp /> Upload & Ingest
                  </>
                )}
              </motion.button>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </PageTransition>
  )
}
