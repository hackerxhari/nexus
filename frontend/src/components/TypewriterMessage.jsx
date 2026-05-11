/**
 * @file TypewriterMessage.jsx
 * @description AI message bubble with a word-by-word typewriter effect and
 *              a citation list (filename + page numbers from RAG retrieval).
 */

import { useEffect, useState } from 'react'
import {
  HiOutlineDocumentText,
  HiOutlineSparkles,
} from 'react-icons/hi2'

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

function formatPages(pages) {
  if (!pages || pages.length === 0) return null
  if (pages.length === 1) return `p. ${pages[0]}`
  // Collapse contiguous ranges, e.g. [1,2,3,5] → "1–3, 5"
  const sorted = [...pages].sort((a, b) => a - b)
  const groups = []
  let start = sorted[0]
  let prev = sorted[0]
  for (let i = 1; i < sorted.length; i++) {
    if (sorted[i] === prev + 1) {
      prev = sorted[i]
      continue
    }
    groups.push(start === prev ? `${start}` : `${start}–${prev}`)
    start = sorted[i]
    prev = sorted[i]
  }
  groups.push(start === prev ? `${start}` : `${start}–${prev}`)
  return `pp. ${groups.join(', ')}`
}

export default function TypewriterMessage({ msg }) {
  const isNew = msg._animate
  const { displayText, isComplete } = useTypewriter(msg.text, 30, isNew)

  const isCustomQA = msg.sources?.length === 1 && msg.sources[0] === 'Custom Q&A'
  const showSources = (isComplete || !isNew) && !isCustomQA
  const citations = msg.citations || []
  const sourceFiles = msg.sources || []

  // Build a quick lookup so a source filename can show its pages
  const pagesByFile = citations.reduce((acc, c) => {
    acc[c.file] = c.pages || []
    return acc
  }, {})

  return (
    <div className="query-msg__content">
      <div className="query-msg__avatar query-msg__avatar--ai">
        <HiOutlineSparkles />
      </div>
      <div className="query-msg__body">
        <div className={`query-msg__text ${!isComplete && isNew ? 'typewriter-cursor' : ''}`}>
          {isNew ? displayText : msg.text}
        </div>
        {showSources && sourceFiles.length > 0 && (
          <div className="query-msg__sources">
            <span className="query-msg__sources-label">
              <HiOutlineDocumentText /> Sources
            </span>
            {sourceFiles.map((s, i) => {
              const pageLabel = formatPages(pagesByFile[s])
              return (
                <span key={i} className="query-msg__source-tag">
                  {s}
                  {pageLabel && (
                    <span className="query-msg__source-pages"> · {pageLabel}</span>
                  )}
                </span>
              )
            })}
          </div>
        )}
        {(isComplete || !isNew) && (
          <div className="query-msg__meta">
            {msg.cached && (
              <span className="query-msg__badge query-msg__badge--cache">Cached</span>
            )}
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
