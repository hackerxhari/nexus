/**
 * @file AuditPage.jsx
 * @description Core React component/service for the Project Nexus application.
 */

import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import {
  HiOutlineShieldCheck,
  HiOutlineCheckCircle,
  HiOutlineXCircle,
  HiOutlineClock,
} from 'react-icons/hi2'
import { adminAPI } from '../services/api'
import PageTransition from '../components/PageTransition'
import toast from 'react-hot-toast'
import './AuditPage.css'

export default function AuditPage() {
  const [logs, setLogs] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    adminAPI.auditLogs(0, 200)
      .then(({ data }) => {
        if (data.success) setLogs(data.data || [])
      })
      .catch(() => toast.error('Failed to load audit logs'))
      .finally(() => setLoading(false))
  }, [])

  return (
    <PageTransition>
      <div className="audit-page">
        <motion.div
          className="page-header"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <h1 className="page-title">
            <HiOutlineShieldCheck style={{ verticalAlign: 'middle' }} /> Audit Logs
          </h1>
          <p className="page-subtitle">Complete query audit trail</p>
        </motion.div>

        {loading ? (
          <div className="docs-loading">
            {[...Array(8)].map((_, i) => (
              <motion.div
                key={i}
                className="docs-skeleton"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: i * 0.05 }}
                style={{ height: 52 }}
              />
            ))}
          </div>
        ) : logs.length === 0 ? (
          <motion.div
            className="docs-empty"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
          >
            <p>No audit logs yet</p>
          </motion.div>
        ) : (
          <div className="audit-table-wrap">
            <table className="users-table audit-table">
              <thead>
                <tr>
                  <th>Status</th>
                  <th>User</th>
                  <th>Question</th>
                  <th>Sources</th>
                  <th>Time</th>
                  <th>Date</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((log, i) => (
                  <motion.tr
                    key={log.id || i}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.02, duration: 0.3 }}
                  >
                    <td>
                      {log.status === 'success' ? (
                        <HiOutlineCheckCircle className="audit-icon audit-icon--ok" />
                      ) : (
                        <HiOutlineXCircle className="audit-icon audit-icon--fail" />
                      )}
                    </td>
                    <td className="audit-user">
                      <span>{log.user_email}</span>
                      <span className="audit-user__roles">
                        {log.user_roles?.join(', ')}
                      </span>
                    </td>
                    <td className="audit-question">
                      {log.question?.substring(0, 80)}{log.question?.length > 80 ? '...' : ''}
                    </td>
                    <td>
                      <div className="audit-sources">
                        {log.sources?.slice(0, 2).map((s, j) => (
                          <span key={j} className="audit-source">{s}</span>
                        ))}
                        {log.sources?.length > 2 && (
                          <span className="audit-source">+{log.sources.length - 2}</span>
                        )}
                      </div>
                    </td>
                    <td className="audit-time">
                      {log.response_time_ms ? `${Math.round(log.response_time_ms)}ms` : '—'}
                      {log.cache_hit && <span className="audit-cached">cached</span>}
                    </td>
                    <td className="users-table__date">
                      {log.asked_at ? new Date(log.asked_at).toLocaleString() : '—'}
                    </td>
                  </motion.tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </PageTransition>
  )
}
