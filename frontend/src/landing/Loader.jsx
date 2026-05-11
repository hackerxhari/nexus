/**
 * @file Loader.jsx
 * @description Core React component/service for the Project Nexus application.
 */

import { useState, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import gsap from 'gsap'
import './Loader.css'

export default function Loader({ onComplete }) {
  const [progress, setProgress] = useState(0)
  const [phase, setPhase] = useState('loading') // loading -> reveal -> done
  const counterRef = useRef(null)
  const barRef = useRef(null)
  const containerRef = useRef(null)
  const wordsRef = useRef(null)

  useEffect(() => {
    // Simulate asset loading with easing
    const obj = { val: 0 }
    const tl = gsap.timeline()

    // Phase 1: Count up with variable speed (fast-slow-fast)
    tl.to(obj, {
      val: 30,
      duration: 0.8,
      ease: 'power2.out',
      onUpdate: () => setProgress(Math.floor(obj.val)),
    })
    .to(obj, {
      val: 65,
      duration: 1.5,
      ease: 'power1.inOut',
      onUpdate: () => setProgress(Math.floor(obj.val)),
    })
    .to(obj, {
      val: 85,
      duration: 0.8,
      ease: 'power2.inOut',
      onUpdate: () => setProgress(Math.floor(obj.val)),
    })
    .to(obj, {
      val: 100,
      duration: 0.6,
      ease: 'power4.in',
      onUpdate: () => setProgress(Math.floor(obj.val)),
      onComplete: () => {
        setPhase('reveal')
        // Reveal animation
        const revealTl = gsap.timeline({
          onComplete: () => {
            setPhase('done')
            setTimeout(onComplete, 100)
          },
        })

        revealTl
          .to(counterRef.current, {
            scale: 1.2,
            duration: 0.3,
            ease: 'power2.in',
          })
          .to(counterRef.current, {
            scale: 40,
            opacity: 0,
            duration: 0.8,
            ease: 'power3.in',
          })
          .to(
            barRef.current,
            { scaleX: 1.5, opacity: 0, duration: 0.5, ease: 'power2.in' },
            '-=0.7'
          )
          .to(
            wordsRef.current,
            { y: -40, opacity: 0, duration: 0.4, ease: 'power2.in' },
            '-=0.6'
          )
          .to(containerRef.current, {
            clipPath: 'circle(150% at 50% 50%)',
            duration: 0.8,
            ease: 'power2.inOut',
          })
          .to(containerRef.current, {
            opacity: 0,
            duration: 0.3,
          })
      },
    })

    return () => tl.kill()
  }, [onComplete])

  if (phase === 'done') return null

  return (
    <div className="loader" ref={containerRef}>
      {/* Background grid */}
      <div className="loader__grid">
        {[...Array(20)].map((_, i) => (
          <motion.div
            key={`v${i}`}
            className="loader__grid-line loader__grid-line--v"
            style={{ left: `${(i + 1) * 5}%` }}
            initial={{ scaleY: 0, opacity: 0 }}
            animate={{ scaleY: 1, opacity: 0.03 }}
            transition={{ delay: i * 0.02, duration: 0.8 }}
          />
        ))}
        {[...Array(20)].map((_, i) => (
          <motion.div
            key={`h${i}`}
            className="loader__grid-line loader__grid-line--h"
            style={{ top: `${(i + 1) * 5}%` }}
            initial={{ scaleX: 0, opacity: 0 }}
            animate={{ scaleX: 1, opacity: 0.03 }}
            transition={{ delay: i * 0.02, duration: 0.8 }}
          />
        ))}
      </div>

      {/* Center content */}
      <div className="loader__center">
        {/* Project name */}
        <div className="loader__words" ref={wordsRef}>
          <motion.span
            initial={{ y: 40, opacity: 0, filter: 'blur(10px)' }}
            animate={{ y: 0, opacity: 1, filter: 'blur(0px)' }}
            transition={{ delay: 0.2, duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
          >
            PROJECT
          </motion.span>
          <motion.span
            className="loader__words-accent"
            initial={{ y: 40, opacity: 0, filter: 'blur(10px)' }}
            animate={{ y: 0, opacity: 1, filter: 'blur(0px)' }}
            transition={{ delay: 0.35, duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
          >
            GREEN
          </motion.span>
        </div>

        {/* Counter */}
        <div className="loader__counter" ref={counterRef}>
          <span className="loader__counter-num">{progress}</span>
          <span className="loader__counter-pct">%</span>
        </div>

        {/* Progress bar */}
        <div className="loader__bar-track" ref={barRef}>
          <motion.div
            className="loader__bar-fill"
            style={{ width: `${progress}%` }}
          />
          <motion.div
            className="loader__bar-glow"
            style={{ left: `${progress}%` }}
            animate={{
              boxShadow: [
                '0 0 20px rgba(34,197,94,0.4)',
                '0 0 40px rgba(34,197,94,0.8)',
                '0 0 20px rgba(34,197,94,0.4)',
              ],
            }}
            transition={{ duration: 1.5, repeat: Infinity }}
          />
        </div>

        {/* Status text */}
        <motion.div
          className="loader__status"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.5 }}
        >
          {progress < 30
            ? 'Initializing neural pathways...'
            : progress < 65
            ? 'Loading knowledge base...'
            : progress < 90
            ? 'Preparing interface...'
            : 'Almost ready...'}
        </motion.div>
      </div>

      {/* Corner accents */}
      <motion.div
        className="loader__corner loader__corner--tl"
        initial={{ opacity: 0, scale: 0 }}
        animate={{ opacity: 0.5, scale: 1 }}
        transition={{ delay: 0.3, duration: 0.6 }}
      />
      <motion.div
        className="loader__corner loader__corner--tr"
        initial={{ opacity: 0, scale: 0 }}
        animate={{ opacity: 0.5, scale: 1 }}
        transition={{ delay: 0.4, duration: 0.6 }}
      />
      <motion.div
        className="loader__corner loader__corner--bl"
        initial={{ opacity: 0, scale: 0 }}
        animate={{ opacity: 0.5, scale: 1 }}
        transition={{ delay: 0.5, duration: 0.6 }}
      />
      <motion.div
        className="loader__corner loader__corner--br"
        initial={{ opacity: 0, scale: 0 }}
        animate={{ opacity: 0.5, scale: 1 }}
        transition={{ delay: 0.6, duration: 0.6 }}
      />
    </div>
  )
}
