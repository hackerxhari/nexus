/**
 * @file useChatPersistence.js
 * @description Stores the current chat thread in localStorage per-user so
 *              messages survive a page refresh. Pulled out of QueryPage.jsx.
 */

import { useEffect } from 'react'

const CHAT_STORAGE_KEY = 'green_chat_messages'
const MAX_STORED_MESSAGES = 100

function getKey(userId) {
  return `${CHAT_STORAGE_KEY}_${userId || 'anon'}`
}

export function useChatPersistence(userId, messages, setMessages) {
  // Load on mount
  useEffect(() => {
    try {
      const stored = localStorage.getItem(getKey(userId))
      if (stored) {
        const parsed = JSON.parse(stored)
        const restored = parsed.map((m) => ({ ...m, _animate: false }))
        setMessages(restored)
      }
    } catch {
      // corrupted storage — start fresh
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userId])

  // Save on change
  useEffect(() => {
    if (messages.length === 0) return
    try {
      const toStore = messages.slice(-MAX_STORED_MESSAGES).map((m) => {
        const { _animate, ...rest } = m
        return rest
      })
      localStorage.setItem(getKey(userId), JSON.stringify(toStore))
    } catch {
      // storage full — ignore
    }
  }, [messages, userId])
}

export function clearStoredChat(userId) {
  try {
    localStorage.removeItem(getKey(userId))
  } catch {
    // ignore
  }
}
