/**
 * @file QueryPage.jsx
 * @description Main chat surface for asking Nexus questions.
 *              Audio capture, STT streaming, chat persistence, and the
 *              typewriter UI live in dedicated hooks/components.
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import {
  HiOutlineMicrophone,
  HiOutlinePaperAirplane,
  HiOutlinePlusCircle,
  HiOutlineSparkles,
} from 'react-icons/hi2'
import toast from 'react-hot-toast'

import { queryAPI, sttAPI } from '../services/api'
import { useAuth } from '../context/AuthContext'
import PageTransition from '../components/PageTransition'
import TypewriterMessage from '../components/TypewriterMessage'
import { useChatPersistence, clearStoredChat } from '../hooks/useChatPersistence'
import { useSttStreaming } from '../hooks/useSttStreaming'
import { formatDuration } from '../utils/audio'
import './QueryPage.css'

const suggestedQuestions = [
  'What is the company leave policy?',
  'How do I submit an expense report?',
  'What are the security guidelines?',
  'Explain the onboarding process',
]

export default function QueryPage() {
  const { user } = useAuth()
  const [question, setQuestion] = useState('')
  const [messages, setMessages] = useState([])
  const [loading, setLoading] = useState(false)
  const [sttAvailable, setSttAvailable] = useState(false)
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)

  useChatPersistence(user?.id, messages, setMessages)

  const handleSttText = useCallback((text, _isFinal) => {
    setQuestion(text)
  }, [])

  const { isRecording, recordingSeconds, start, stop, prewarm, teardown } =
    useSttStreaming({ onText: handleSttText, enabled: sttAvailable })

  // Check STT availability and prewarm once
  useEffect(() => {
    let cancelled = false
    sttAPI.status()
      .then(({ data }) => {
        if (cancelled) return
        const available = data?.data?.available || false
        setSttAvailable(available)
        if (available) prewarm()
      })
      .catch(() => !cancelled && setSttAvailable(false))

    return () => {
      cancelled = true
      teardown()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Auto-scroll on new message
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const getConversationHistory = useCallback(() => {
    const recentMessages = messages.slice(-6) // last 3 turns
    return recentMessages
      .filter((m) => m.type === 'user' || m.type === 'ai')
      .map((m) => ({
        role: m.type === 'user' ? 'user' : 'assistant',
        content: m.text,
      }))
  }, [messages])

  const handleAsk = async (q) => {
    const text = q || question.trim()
    if (!text || loading) return

    const userMsg = { type: 'user', text, id: Date.now() }
    setMessages((prev) => [...prev, userMsg])
    setQuestion('')
    setLoading(true)

    try {
      const history = getConversationHistory()
      const { data } = await queryAPI.ask(
        text,
        null,
        false,
        history.length > 0 ? history : null,
      )
      if (data.success) {
        const aiMsg = {
          type: 'ai',
          text: data.data.answer,
          sources: data.data.sources,
          citations: data.data.citations || [],
          chunks: data.data.chunks_retrieved,
          cached: data.data.cache_hit,
          performance: data.data.performance,
          id: Date.now() + 1,
          _animate: true,
        }
        setMessages((prev) => [...prev, aiMsg])
      } else {
        toast.error(data.error?.message || 'Query failed')
        setMessages((prev) => [
          ...prev,
          { type: 'error', text: data.error?.message || 'Something went wrong', id: Date.now() + 1 },
        ])
      }
    } catch (err) {
      const msg = err.response?.data?.error?.message || 'Network error'
      toast.error(msg)
      setMessages((prev) => [...prev, { type: 'error', text: msg, id: Date.now() + 1 }])
    } finally {
      setLoading(false)
      inputRef.current?.focus()
    }
  }

  const handleMicToggle = async () => {
    if (isRecording) {
      await stop()
      return
    }
    await start(question)
  }

  const handleNewChat = () => {
    setMessages([])
    setQuestion('')
    clearStoredChat(user?.id)
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleAsk()
    }
  }

  return (
    <PageTransition>
      <div className="query-page">
        {messages.length > 0 && (
          <motion.div
            className="query-header-actions"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
          >
            <button
              className="query-header-btn"
              onClick={handleNewChat}
              title="New Chat"
            >
              <HiOutlinePlusCircle /> New Chat
            </button>
          </motion.div>
        )}

        {messages.length === 0 && (
          <motion.div
            className="query-empty"
            initial={{ opacity: 0, y: 40 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
          >
            <motion.div
              className="query-empty__icon"
              animate={{ rotate: [0, 10, -10, 0] }}
              transition={{ duration: 4, repeat: Infinity, ease: 'easeInOut' }}
            >
              <HiOutlineSparkles />
            </motion.div>
            <h1 className="query-empty__title">What would you like to know?</h1>
            <p className="query-empty__subtitle">
              Ask anything about your organization's knowledge base. Answers are filtered by your role.
            </p>
            <div className="query-suggestions">
              {suggestedQuestions.map((q, i) => (
                <motion.button
                  key={q}
                  className="query-suggestion"
                  onClick={() => handleAsk(q)}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.3 + i * 0.1, duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
                  whileHover={{ scale: 1.02, y: -2 }}
                  whileTap={{ scale: 0.98 }}
                >
                  {q}
                </motion.button>
              ))}
            </div>
          </motion.div>
        )}

        {messages.length > 0 && (
          <div className="query-messages">
            <AnimatePresence>
              {messages.map((msg) => (
                <motion.div
                  key={msg.id}
                  className={`query-msg query-msg--${msg.type}`}
                  initial={{ opacity: 0, y: 20, scale: 0.97 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
                  layout
                >
                  {msg.type === 'user' && (
                    <div className="query-msg__content">
                      <div className="query-msg__avatar">
                        {user?.full_name?.charAt(0) || '?'}
                      </div>
                      <div className="query-msg__text">{msg.text}</div>
                    </div>
                  )}
                  {msg.type === 'ai' && <TypewriterMessage msg={msg} />}
                  {msg.type === 'error' && (
                    <div className="query-msg__content">
                      <div className="query-msg__avatar query-msg__avatar--error">!</div>
                      <div className="query-msg__text query-msg__text--error">{msg.text}</div>
                    </div>
                  )}
                </motion.div>
              ))}
            </AnimatePresence>

            {loading && (
              <motion.div
                className="query-msg query-msg--ai"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
              >
                <div className="query-msg__content">
                  <div className="query-msg__avatar query-msg__avatar--ai">
                    <HiOutlineSparkles />
                  </div>
                  <div className="query-typing">
                    <span /><span /><span />
                  </div>
                </div>
              </motion.div>
            )}
            <div ref={messagesEndRef} />
          </div>
        )}

        <motion.div
          className="query-input-wrap"
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2, duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
        >
          {isRecording && (
            <div className="query-listening">
              <div className="listening-orb" aria-hidden="true" />
              <div className="query-listening__text">Listening...</div>
              <div className="query-listening__timer">{formatDuration(recordingSeconds)}</div>
            </div>
          )}
          <div className="query-input">
            {sttAvailable && (
              <motion.button
                className={`query-input__mic ${isRecording ? 'query-input__mic--recording' : ''}`}
                onClick={handleMicToggle}
                whileHover={{ scale: 1.08 }}
                whileTap={{ scale: 0.92 }}
                title={isRecording ? 'Stop recording' : 'Start voice input'}
              >
                <HiOutlineMicrophone />
                {isRecording && <span className="mic-pulse" />}
              </motion.button>
            )}
            <textarea
              ref={inputRef}
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={isRecording ? 'Listening...' : 'Ask a question...'}
              rows={1}
              disabled={loading}
            />
            <motion.button
              className="query-input__send"
              onClick={() => handleAsk()}
              disabled={!question.trim() || loading}
              whileHover={{ scale: 1.08 }}
              whileTap={{ scale: 0.92 }}
            >
              <HiOutlinePaperAirplane />
            </motion.button>
          </div>
          <p className="query-input__hint">
            Press Enter to send · Shift+Enter for new line
            {sttAvailable && ' · Voice input available'}
          </p>
        </motion.div>
      </div>
    </PageTransition>
  )
}
