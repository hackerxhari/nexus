/**
 * @file GlowOrb.jsx
 * @description Core React component/service for the Project Nexus application.
 */

import { motion } from 'framer-motion'
import './GlowOrb.css'

export default function GlowOrb({ color = 'var(--accent)', size = 400, x = '50%', y = '30%', delay = 0 }) {
  return (
    <motion.div
      className="glow-orb"
      initial={{ opacity: 0, scale: 0.5 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 2, delay, ease: 'easeOut' }}
      style={{
        width: size,
        height: size,
        left: x,
        top: y,
        background: `radial-gradient(circle, ${color} 0%, transparent 70%)`,
      }}
    />
  )
}
