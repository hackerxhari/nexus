/**
 * @file useSttStreaming.js
 * @description Owns the microphone + WebSocket lifecycle for live STT.
 * Returns a small API: { isRecording, recordingSeconds, start, stop, prewarm, teardown }.
 * Pulled out of QueryPage.jsx so the page can focus on UI concerns.
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import toast from 'react-hot-toast'

import {
  SILENCE_THRESHOLD,
  SILENCE_TIMEOUT_MS,
  STREAM_BUFFER_SIZE,
  TARGET_SAMPLE_RATE,
  computeRms,
  floatTo16BitPCM,
  normalize,
  resample,
} from '../utils/audio'
import { getValidAccessToken } from '../utils/auth'

export function useSttStreaming({ onText, enabled }) {
  const [isRecording, setIsRecording] = useState(false)
  const [recordingSeconds, setRecordingSeconds] = useState(0)

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
  const onTextRef = useRef(onText)

  useEffect(() => {
    onTextRef.current = onText
  }, [onText])

  const updateStreamingText = useCallback((text, isFinal) => {
    if (!text && !isFinal) return
    const base = baseTextRef.current

    if (isFinal) {
      const nextBase = [base, text].filter(Boolean).join(' ').trim()
      baseTextRef.current = nextBase
      partialTextRef.current = ''
      onTextRef.current?.(nextBase, true)
      return
    }

    partialTextRef.current = text
    const combined = [base, text].filter(Boolean).join(' ')
    onTextRef.current?.(combined, false)
  }, [])

  const stop = useCallback(async (sendStop = true) => {
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
  }, [])

  const teardown = useCallback(async () => {
    prewarmWsRef.current?.close()
    prewarmWsRef.current = null

    prewarmContextRef.current?.close()
    prewarmContextRef.current = null

    prewarmStreamRef.current?.getTracks().forEach((t) => t.stop())
    prewarmStreamRef.current = null

    isPrewarmedRef.current = false
  }, [])

  const prewarm = useCallback(async () => {
    if (isPrewarmedRef.current || !enabled) return

    const token = getValidAccessToken()
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const params = new URLSearchParams({
      sample_rate: TARGET_SAMPLE_RATE.toString(),
      prewarm: '1',
    })
    if (token) params.set('token', token)
    const wsUrl = `${protocol}://${window.location.host}/api/v1/stt/stream?${params.toString()}`

    const ws = new WebSocket(wsUrl)
    ws.binaryType = 'arraybuffer'
    prewarmWsRef.current = ws

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
  }, [enabled])

  const start = useCallback(async (initialText = '') => {
    if (isRecording) return

    isStreamingRef.current = true
    baseTextRef.current = initialText.trim()
    partialTextRef.current = ''
    silenceMsRef.current = 0
    hasSpokenRef.current = false

    const token = getValidAccessToken()
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const params = new URLSearchParams({ sample_rate: TARGET_SAMPLE_RATE.toString() })
    if (token) params.set('token', token)
    const wsUrl = `${protocol}://${window.location.host}/api/v1/stt/stream?${params.toString()}`

    await teardown()

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
            stop()
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
    } catch {
      toast.error('Microphone access denied')
      await stop(false)
    }
  }, [isRecording, stop, teardown, updateStreamingText])

  // Recording timer
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

  return { isRecording, recordingSeconds, start, stop, prewarm, teardown }
}
