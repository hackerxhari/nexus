/**
 * @file MagneticCursor.jsx
 * @description Core React component/service for the Project Nexus application.
 */

import { useEffect, useRef, useState } from 'react'
import { motion } from 'framer-motion'
import './MagneticCursor.css'

export default function MagneticCursor() {
  const cursorRef = useRef(null)
  const followerRef = useRef(null)
  const [hovering, setHovering] = useState(false)
  const pos = useRef({ x: -100, y: -100 })
  const followerPos = useRef({ x: -100, y: -100 })

  useEffect(() => {
    const move = (e) => {
      pos.current = { x: e.clientX, y: e.clientY }
    }

    const over = (e) => {
      const target = e.target.closest('[data-magnetic]') || e.target.closest('a, button')
      setHovering(!!target)
    }

    window.addEventListener('mousemove', move)
    window.addEventListener('mouseover', over)

    let raf
    const animate = () => {
      if (cursorRef.current) {
        cursorRef.current.style.transform = `translate(${pos.current.x}px, ${pos.current.y}px)`
      }

      // Smooth follower
      followerPos.current.x += (pos.current.x - followerPos.current.x) * 0.12
      followerPos.current.y += (pos.current.y - followerPos.current.y) * 0.12

      if (followerRef.current) {
        followerRef.current.style.transform = `translate(${followerPos.current.x}px, ${followerPos.current.y}px)`
      }

      raf = requestAnimationFrame(animate)
    }
    raf = requestAnimationFrame(animate)

    return () => {
      window.removeEventListener('mousemove', move)
      window.removeEventListener('mouseover', over)
      cancelAnimationFrame(raf)
    }
  }, [])

  return (
    <>
      <div
        ref={cursorRef}
        className={`custom-cursor ${hovering ? 'custom-cursor--hover' : ''}`}
      />
      <div
        ref={followerRef}
        className={`custom-cursor-follower ${hovering ? 'custom-cursor-follower--hover' : ''}`}
      />
    </>
  )
}
