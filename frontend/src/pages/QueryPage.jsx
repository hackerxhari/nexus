/**
 * @file QueryPage.jsx
 * @description Core React component/service for the Project Nexus application.
 */

import { useState, useRef, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  HiOutlinePaperAirplane,
  HiOutlineSparkles,
  HiOutlineDocumentText,
  HiOutlineMicrophone,
  HiOutlineTrash,
  HiOutlinePlusCircle,
} from 'react-icons/hi2'
import { queryAPI, sttAPI } from '../services/api'
import { useAuth } from '../context/AuthContext'
import PageTransition from '../components/PageTransition'
import toast from 'react-hot-toast'
import './QueryPage.css'

const suggestedQuestions = [
  'What is the company leave policy?',
  'How do I submit an expense report?',
  'What are the security guidelines?',
  'Explain the onboarding process',
]

const CHAT_STORAGE_KEY = 'green_chat_messages'
const MAX_STORED_MESSAGES = 100

const TARGET_SAMPLE_RATE = 16000
const STREAM_BUFFER_SIZE = 4096
const SILENCE_THRESHOLD = 0.008
const SILENCE_TIMEOUT_MS = 3000

// ── Typewriter Hook ──────────────────────────────────────
function useTypewriter(text, speed = 20, enabled = true) {
  const [displayText, setDisplayText] = useState('')
  const [isComplete, setIsComplete] = useState(false)

  useEffect(() => {
    if (!enabled || !text) {
      setDisplayText(text || '')
      setIsComplete(true)
      return
    }

    setDisplayText('')
    setIsComplete(false)

    const words = text.split(' ')
    let currentIdx = 0

    const timer = setInterval(() => {
      currentIdx++
      setDisplayText(words.slice(0, currentIdx).join(' '))
      if (currentIdx >= words.length) {
        setIsComplete(true)
        clearInterval(timer)
      }
    }, speed)

    return () => clearInterval(timer)
  }, [text, speed, enabled])

  return { displayText, isComplete }
}

// ── Typewriter Message Component ──────────────────────────
function TypewriterMessage({ msg, user }) {
  const isNew = msg._animate
  const { displayText, isComplete } = useTypewriter(msg.text, 30, isNew)

  const isCustomQA = msg.sources?.length === 1 && msg.sources[0] === 'Custom Q&A'

  return (
    <div className="query-msg__content">
      <div className="query-msg__avatar query-msg__avatar--ai">
        <HiOutlineSparkles />
      </div>
      <div className="query-msg__body">
        <div className={`query-msg__text ${!isComplete && isNew ? 'typewriter-cursor' : ''}`}>
          {isNew ? displayText : msg.text}
        </div>
        {(isComplete || !isNew) && !isCustomQA && msg.sources?.length > 0 && (
          <div className="query-msg__sources">
            <span className="query-msg__sources-label">
              <HiOutlineDocumentText /> Sources
            </span>
            {msg.sources.map((s, i) => (
              <span key={i} className="query-msg__source-tag">{s}</span>
            ))}
          </div>
        )}
        {(isComplete || !isNew) && (
          <div className="query-msg__meta">
            {msg.cached && <span className="query-msg__badge query-msg__badge--cache">Cached</span>}
            {!isCustomQA && msg.chunks > 0 && (
              <span className="query-msg__badge">{msg.chunks} chunks</span>
            )}
            {isCustomQA && (
              <span className="query-msg__badge query-msg__badge--cache">Instant Answer</span>
            )}
            {msg.performance?.response_time_ms && (
              <span className="query-msg__badge">
                {Math.round(msg.performance.response_time_ms)}ms
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

// ── Main QueryPage ────────────────────────────────────────
export default function QueryPage() {
  const { user } = useAuth()
  const [question, setQuestion] = useState('')
  const [messages, setMessages] = useState([])
  const [loading, setLoading] = useState(false)
  const [isRecording, setIsRecording] = useState(false)
  const [sttAvailable, setSttAvailable] = useState(false)
  const [recordingSeconds, setRecordingSeconds] = useState(0)
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)
  const mediaRecorderRef = useRef(null)
  const audioChunksRef = useRef([])
  const audioContextRef = useRef(null)
  const prewarmContextRef = useRef(null)
  const prewarmStreamRef = useRef(null)
  const processorRef = useRef(null)
  const mediaStreamRef = useRef(null)
  const wsRef = useRef(null)
  const prewarmWsRef = useRef(null)
  const isPrewarmedRef = useRef(false)
  const isStreamingRef = useRef(false)
  const audioQueueRef = useRef([])
  const silenceMsRef = useRef(0)
  const hasSpokenRef = useRef(false)
  const baseTextRef = useRef('')
  const partialTextRef = useRef('')
  const timerRef = useRef(null)

  const toMono = (audioBuffer) => {
    if (audioBuffer.numberOfChannels === 1) {
      return audioBuffer.getChannelData(0)
    }

    const left = audioBuffer.getChannelData(0)
    const right = audioBuffer.getChannelData(1)
    const mono = new Float32Array(left.length)
    for (let i = 0; i < left.length; i++) {
      mono[i] = (left[i] + right[i]) / 2
    }
    return mono
  }

  const resample = (input, inputSampleRate, outputSampleRate) => {
    if (inputSampleRate === outputSampleRate) return input

    const ratio = inputSampleRate / outputSampleRate
    const outputLength = Math.round(input.length / ratio)
    const output = new Float32Array(outputLength)

    for (let i = 0; i < outputLength; i++) {
      const position = i * ratio
      const leftIndex = Math.floor(position)
      const rightIndex = Math.min(leftIndex + 1, input.length - 1)
      const weight = position - leftIndex
      output[i] = input[leftIndex] * (1 - weight) + input[rightIndex] * weight
    }

    return output
  }

  const normalize = (samples) => {
    let peak = 0
    for (let i = 0; i < samples.length; i++) {
      const abs = Math.abs(samples[i])
      if (abs > peak) peak = abs
    }
    if (peak === 0) return samples

    const scale = Math.min(10, 0.98 / peak)
    if (Math.abs(scale - 1) < 1e-3) return samples

    const output = new Float32Array(samples.length)
    for (let i = 0; i < samples.length; i++) {
      output[i] = samples[i] * scale
    }
    return output
  }

  const encodeWav = (samples, sampleRate) => {
    const buffer = new ArrayBuffer(44 + samples.length * 2)
    const view = new DataView(buffer)

    const writeString = (offset, str) => {
      for (let i = 0; i < str.length; i++) {
        view.setUint8(offset + i, str.charCodeAt(i))
      }
    }

    let offset = 0
    writeString(offset, 'RIFF')
    offset += 4
    view.setUint32(offset, 36 + samples.length * 2, true)
    offset += 4
    writeString(offset, 'WAVE')
    offset += 4
    writeString(offset, 'fmt ')
    offset += 4
    view.setUint32(offset, 16, true)
    offset += 4
    view.setUint16(offset, 1, true)
    offset += 2
    view.setUint16(offset, 1, true)
    offset += 2
    view.setUint32(offset, sampleRate, true)
    offset += 4
    view.setUint32(offset, sampleRate * 2, true)
    offset += 4
    view.setUint16(offset, 2, true)
    offset += 2
    view.setUint16(offset, 16, true)
    offset += 2
    writeString(offset, 'data')
    offset += 4
    view.setUint32(offset, samples.length * 2, true)
    offset += 4

    for (let i = 0; i < samples.length; i++, offset += 2) {
      const s = Math.max(-1, Math.min(1, samples[i]))
      view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true)
    }

    return new Blob([buffer], { type: 'audio/wav' })
  }

  const formatDuration = (seconds) => {
    const mins = Math.floor(seconds / 60)
    const secs = Math.floor(seconds % 60)
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
  }

  const getValidAccessToken = () => {
    const token = localStorage.getItem('access_token')
    if (!token) return null

    try {
      const payload = JSON.parse(atob(token.split('.')[1]))
      if (!payload?.exp) return token
      const now = Math.floor(Date.now() / 1000)
      if (payload.exp <= now) return null
      return token
    } catch {
      return null
    }
  }

  const floatTo16BitPCM = (samples) => {
    const buffer = new ArrayBuffer(samples.length * 2)
    const view = new DataView(buffer)
    for (let i = 0; i < samples.length; i++) {
      const s = Math.max(-1, Math.min(1, samples[i]))
      view.setInt16(i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true)
    }
    return buffer
  }

  const computeRms = (samples) => {
    if (!samples.length) return 0
    let sum = 0
    for (let i = 0; i < samples.length; i++) {
      sum += samples[i] * samples[i]
    }
    return Math.sqrt(sum / samples.length)
  }

  const convertToWav = async (blob, targetSampleRate) => {
    const audioContext = new (window.AudioContext || window.webkitAudioContext)()
    try {
      const arrayBuffer = await blob.arrayBuffer()
      const decoded = await audioContext.decodeAudioData(arrayBuffer)
      const mono = toMono(decoded)
      const resampled = resample(mono, decoded.sampleRate, targetSampleRate)
      const normalized = normalize(resampled)
      return encodeWav(normalized, targetSampleRate)
    } finally {
      await audioContext.close()
    }
  }

  const updateStreamingText = (text, isFinal) => {
    if (!text && !isFinal) return
    const base = baseTextRef.current

    if (isFinal) {
      const nextBase = [base, text].filter(Boolean).join(' ').trim()
      baseTextRef.current = nextBase
      partialTextRef.current = ''
      setQuestion(nextBase)
      return
    }

    partialTextRef.current = text
    const combined = [base, text].filter(Boolean).join(' ')
    setQuestion(combined)
  }

  const stopStreaming = async (sendStop = true) => {
    isStreamingRef.current = false
    if (sendStop && wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send('stop')
    }

    wsRef.current?.close()
    wsRef.current = null
    audioQueueRef.current = []

    if (processorRef.current) {
      processorRef.current.onaudioprocess = null
      processorRef.current.disconnect()
    }
    processorRef.current = null

    if (audioContextRef.current) {
      try {
        await audioContextRef.current.close()
      } catch {
        // ignore close errors
      }
      audioContextRef.current = null
    }

    mediaStreamRef.current?.getTracks().forEach((t) => t.stop())
    mediaStreamRef.current = null

    setIsRecording(false)
  }

  const prewarmStreaming = async () => {
    if (isPrewarmedRef.current || !sttAvailable) return

    const token = getValidAccessToken()
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const params = new URLSearchParams({ sample_rate: TARGET_SAMPLE_RATE.toString(), prewarm: '1' })
    if (token) params.set('token', token)
    const wsUrl = `${protocol}://${window.location.host}/api/v1/stt/stream?${params.toString()}`

    const ws = new WebSocket(wsUrl)
    ws.binaryType = 'arraybuffer'
    prewarmWsRef.current = ws

    ws.onopen = () => {
      // keep connection ready
    }

    ws.onclose = () => {
      prewarmWsRef.current = null
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      prewarmStreamRef.current = stream

      const audioContext = new (window.AudioContext || window.webkitAudioContext)({
        sampleRate: TARGET_SAMPLE_RATE,
      })
      prewarmContextRef.current = audioContext

      const source = audioContext.createMediaStreamSource(stream)
      const processor = audioContext.createScriptProcessor(STREAM_BUFFER_SIZE, 1, 1)
      const muteGain = audioContext.createGain()
      muteGain.gain.value = 0

      processor.onaudioprocess = (event) => {
        const input = event.inputBuffer.getChannelData(0)
        const normalized = normalize(input)
        const pcm = floatTo16BitPCM(normalized)
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(pcm)
        }
      }

      source.connect(processor)
      processor.connect(muteGain)
      muteGain.connect(audioContext.destination)

      isPrewarmedRef.current = true
    } catch {
      // Ignore if user denies mic; streaming will still work when requested
    }
  }

  const teardownPrewarm = async () => {
    prewarmWsRef.current?.close()
    prewarmWsRef.current = null

    prewarmContextRef.current?.close()
    prewarmContextRef.current = null

    prewarmStreamRef.current?.getTracks().forEach((t) => t.stop())
    prewarmStreamRef.current = null

    isPrewarmedRef.current = false
  }

  const startStreaming = async () => {
    if (isRecording) return

    isStreamingRef.current = true

    baseTextRef.current = question.trim()
    partialTextRef.current = ''
    silenceMsRef.current = 0
    hasSpokenRef.current = false

    const token = getValidAccessToken()
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const params = new URLSearchParams({ sample_rate: TARGET_SAMPLE_RATE.toString() })
    if (token) params.set('token', token)
    const wsUrl = `${protocol}://${window.location.host}/api/v1/stt/stream?${params.toString()}`

    await teardownPrewarm()

    const ws = new WebSocket(wsUrl)
    ws.binaryType = 'arraybuffer'
    wsRef.current = ws

    ws.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data)
        if (payload.type === 'partial') {
          updateStreamingText(payload.text || '', false)
        }
        if (payload.type === 'final') {
          updateStreamingText(payload.text || '', true)
        }
        if (payload.type === 'error') {
          toast.error(payload.message || 'Streaming error')
        }
      } catch {
        // ignore non-json messages
      }
    }

    ws.onerror = () => {
      toast.error('Streaming connection failed')
    }

    ws.onclose = () => {
      setIsRecording(false)
    }

    ws.onopen = () => {
      const queued = audioQueueRef.current
      audioQueueRef.current = []
      queued.forEach((chunk) => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(chunk)
        }
      })
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      mediaStreamRef.current = stream

      const audioContext = new (window.AudioContext || window.webkitAudioContext)({
        sampleRate: TARGET_SAMPLE_RATE,
      })
      audioContextRef.current = audioContext

      const source = audioContext.createMediaStreamSource(stream)
      const processor = audioContext.createScriptProcessor(STREAM_BUFFER_SIZE, 1, 1)
      processorRef.current = processor

      processor.onaudioprocess = (event) => {
        if (!isStreamingRef.current) return
        const input = event.inputBuffer.getChannelData(0)
        const rms = computeRms(input)
        if (rms > SILENCE_THRESHOLD) {
          hasSpokenRef.current = true
          silenceMsRef.current = 0
        } else if (hasSpokenRef.current) {
          silenceMsRef.current += (input.length / audioContext.sampleRate) * 1000
          if (silenceMsRef.current >= SILENCE_TIMEOUT_MS) {
            stopStreaming()
            return
          }
        }

        const resampled = audioContext.sampleRate === TARGET_SAMPLE_RATE
          ? input
          : resample(input, audioContext.sampleRate, TARGET_SAMPLE_RATE)
        const normalized = normalize(resampled)
        const pcm = floatTo16BitPCM(normalized)

        if (ws.readyState === WebSocket.OPEN) {
          ws.send(pcm)
        } else {
          const queue = audioQueueRef.current
          if (queue.length < 50) {
            queue.push(pcm)
          }
        }
      }

      const muteGain = audioContext.createGain()
      muteGain.gain.value = 0

      source.connect(processor)
      processor.connect(muteGain)
      muteGain.connect(audioContext.destination)
      setIsRecording(true)
    } catch (err) {
      toast.error('Microphone access denied')
      await stopStreaming(false)
    }
  }

  // ── Load chat from localStorage ──────────────────
  useEffect(() => {
    try {
      const key = `${CHAT_STORAGE_KEY}_${user?.id || 'anon'}`
      const stored = localStorage.getItem(key)
      if (stored) {
        const parsed = JSON.parse(stored)
        // Mark all restored messages as not needing animation
        const restored = parsed.map((m) => ({ ...m, _animate: false }))
        setMessages(restored)
      }
    } catch {
      // corrupted storage — start fresh
    }
  }, [user?.id])

  // ── Save chat to localStorage ─────────────────────
  useEffect(() => {
    if (messages.length === 0) return
    try {
      const key = `${CHAT_STORAGE_KEY}_${user?.id || 'anon'}`
      const toStore = messages.slice(-MAX_STORED_MESSAGES).map((m) => {
        const { _animate, ...rest } = m
        return rest
      })
      localStorage.setItem(key, JSON.stringify(toStore))
    } catch {
      // storage full — ignore
    }
  }, [messages, user?.id])

  // ── Check STT availability ────────────────────────
  useEffect(() => {
    sttAPI.status()
      .then(({ data }) => {
        const available = data?.data?.available || false
        setSttAvailable(available)
        if (available) {
          prewarmStreaming()
        }
      })
      .catch(() => setSttAvailable(false))

    return () => {
      teardownPrewarm()
    }
  }, [])

  // ── Auto-scroll ──────────────────────────────────
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // ── Recording timer ─────────────────────────────
  useEffect(() => {
    if (!isRecording) {
      setRecordingSeconds(0)
      if (timerRef.current) {
        clearInterval(timerRef.current)
        timerRef.current = null
      }
      return
    }

    setRecordingSeconds(0)
    timerRef.current = setInterval(() => {
      setRecordingSeconds((prev) => prev + 1)
    }, 1000)

    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current)
        timerRef.current = null
      }
    }
  }, [isRecording])

  // ── Build conversation history for context ────────
  const getConversationHistory = useCallback(() => {
    const recentMessages = messages.slice(-6) // last 3 turns
    return recentMessages
      .filter((m) => m.type === 'user' || m.type === 'ai')
      .map((m) => ({
        role: m.type === 'user' ? 'user' : 'assistant',
        content: m.text,
      }))
  }, [messages])

  // ── Handle Ask ───────────────────────────────────
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
        history.length > 0 ? history : null
      )
      if (data.success) {
        const aiMsg = {
          type: 'ai',
          text: data.data.answer,
          sources: data.data.sources,
          chunks: data.data.chunks_retrieved,
          cached: data.data.cache_hit,
          performance: data.data.performance,
          id: Date.now() + 1,
          _animate: true, // trigger typewriter
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
      setMessages((prev) => [
        ...prev,
        { type: 'error', text: msg, id: Date.now() + 1 },
      ])
    } finally {
      setLoading(false)
      inputRef.current?.focus()
    }
  }

  // ── Handle Mic Recording ─────────────────────────
  const handleMicToggle = async () => {
    if (isRecording) {
      await stopStreaming()
      return
    }

    await startStreaming()
  }

  // ── New Chat ─────────────────────────────────────
  const handleNewChat = () => {
    setMessages([])
    setQuestion('')
    try {
      const key = `${CHAT_STORAGE_KEY}_${user?.id || 'anon'}`
      localStorage.removeItem(key)
    } catch { }
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
        {/* Header actions */}
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

        {/* Empty state */}
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
            <h1 className="query-empty__title">
              What would you like to know?
            </h1>
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

        {/* Messages */}
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
                  {msg.type === 'ai' && (
                    <TypewriterMessage msg={msg} user={user} />
                  )}
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

        {/* Input */}
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
            {sttAvailable && ' · 🎤 Voice input available'}
          </p>
        </motion.div>
      </div>
    </PageTransition>
  )
}
