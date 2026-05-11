/**
 * @file HistoryPage.jsx
 * @description Core React component/service for the Project Nexus application.
 */

import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { HiOutlineChartBarSquare, HiOutlineClock } from 'react-icons/hi2'
import { queryAPI } from '../services/api'
import PageTransition from '../components/PageTransition'
import toast from 'react-hot-toast'
import './HistoryPage.css'

export default function HistoryPage() {
  const [history, setHistory] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    queryAPI.history(0, 100)
      .then(({ data }) => {
        if (data.success) setHistory(data.data || [])
      })
      .catch(() => toast.error('Failed to load history'))
      .finally(() => setLoading(false))
  }, [])

  return (
    <PageTransition>
      <div className="history-page">
        <motion.div
          className="page-header"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <h1 className="page-title">
            <HiOutlineChartBarSquare style={{ verticalAlign: 'middle' }} /> Query History
          </h1>
          <p className="page-subtitle">Your recent queries and responses</p>
        </motion.div>

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
        ) : history.length === 0 ? (
          <motion.div
            className="docs-empty"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
          >
            <p>No queries yet. Ask a question to get started!</p>
          </motion.div>
        ) : (
          <div className="history-list">
            {history.map((item, i) => (
              <motion.div
                key={item.id || i}
                className="history-item"
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.04, duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
                whileHover={{ x: 4 }}
              >
                <div className="history-item__q">
                  <span className="history-item__label">Q</span>
                  <span>{item.question}</span>
                </div>
                {item.answer && (
                  <div className="history-item__a">
                    <span className="history-item__label history-item__label--ai">A</span>
                    <span>{item.answer?.substring(0, 200)}{item.answer?.length > 200 ? '...' : ''}</span>
                  </div>
                )}
                <div className="history-item__meta">
                  {item.asked_at && (
                    <span className="history-item__time">
                      <HiOutlineClock /> {new Date(item.asked_at).toLocaleString()}
                    </span>
                  )}
                  {item.cache_hit && <span className="history-item__badge">cached</span>}
                  {item.response_time_ms && (
                    <span className="history-item__badge">{Math.round(item.response_time_ms)}ms</span>
                  )}
                  {item.sources?.length > 0 && (
                    <span className="history-item__badge">{item.sources.length} sources</span>
                  )}
                </div>
              </motion.div>
            ))}
          </div>
        )}
      </div>
    </PageTransition>
  )
}
