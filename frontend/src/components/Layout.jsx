/**
 * @file Layout.jsx
 * @description Core React component/service for the Project Nexus application.
 */

import { Outlet } from 'react-router-dom'
import { AnimatePresence } from 'framer-motion'
import Sidebar from './Sidebar'
import GlowOrb from './GlowOrb'
import './Layout.css'

export default function Layout() {
  return (
    <div className="layout">
      <GlowOrb color="var(--accent)" size={600} x="70%" y="20%" delay={0} />
      <GlowOrb color="#3b82f6" size={400} x="20%" y="80%" delay={0.5} />
      <Sidebar />
      <main className="layout__main">
        <AnimatePresence mode="wait">
          <Outlet />
        </AnimatePresence>
      </main>
    </div>
  )
}
