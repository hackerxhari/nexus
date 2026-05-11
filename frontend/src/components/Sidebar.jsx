/**
 * @file Sidebar.jsx
 * @description Core React component/service for the Project Nexus application.
 */

import { NavLink, useLocation } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { useState } from 'react'
import {
  HiOutlineChatBubbleLeftRight,
  HiOutlineDocumentArrowUp,
  HiOutlineRectangleStack,
  HiOutlineUsers,
  HiOutlineShieldCheck,
  HiOutlineChartBarSquare,
  HiOutlineArrowRightOnRectangle,
  HiOutlineBars3,
  HiOutlineXMark,
  HiOutlineQuestionMarkCircle,
  HiOutlineBuildingOffice2,
} from 'react-icons/hi2'
import { useAuth } from '../context/AuthContext'
import './Sidebar.css'

const navItems = [
  { to: '/', icon: HiOutlineChatBubbleLeftRight, label: 'Ask', end: true },
  { to: '/documents', icon: HiOutlineRectangleStack, label: 'Documents' },
  { to: '/upload', icon: HiOutlineDocumentArrowUp, label: 'Upload' },
  { to: '/history', icon: HiOutlineChartBarSquare, label: 'History' },
  { to: '/custom-qa', icon: HiOutlineQuestionMarkCircle, label: 'Custom Q&A', admin: true },
  { to: '/departments', icon: HiOutlineBuildingOffice2, label: 'Departments', admin: true },
  { to: '/users', icon: HiOutlineUsers, label: 'Users', managerPlus: true },
  { to: '/audit', icon: HiOutlineShieldCheck, label: 'Audit', managerPlus: true },
]

export default function Sidebar() {
  const { user, logout, isAdmin, isManagement } = useAuth()
  const location = useLocation()
  const [collapsed, setCollapsed] = useState(false)

  const filtered = navItems.filter((n) => {
    if (n.managerPlus) return isManagement;
    if (n.admin) return isAdmin;
    return true;
  })

  return (
    <>
      {/* Mobile toggle */}
      <button className="sidebar-mobile-toggle" onClick={() => setCollapsed(!collapsed)}>
        {collapsed ? <HiOutlineXMark /> : <HiOutlineBars3 />}
      </button>

      <motion.aside
        className={`sidebar ${collapsed ? 'sidebar--open' : ''}`}
        initial={{ x: -80, opacity: 0 }}
        animate={{ x: 0, opacity: 1 }}
        transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
      >
        {/* Logo */}
        <div className="sidebar__logo">
          <motion.div
            className="sidebar__logo-icon"
            whileHover={{ rotate: 180, scale: 1.1 }}
            transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
          >
            <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
              <circle cx="14" cy="14" r="12" stroke="var(--accent)" strokeWidth="2" />
              <circle cx="14" cy="14" r="5" fill="var(--accent)" />
              <path d="M14 2 L14 8" stroke="var(--accent)" strokeWidth="2" strokeLinecap="round" />
              <path d="M14 20 L14 26" stroke="var(--accent)" strokeWidth="2" strokeLinecap="round" />
              <path d="M2 14 L8 14" stroke="var(--accent)" strokeWidth="2" strokeLinecap="round" />
              <path d="M20 14 L26 14" stroke="var(--accent)" strokeWidth="2" strokeLinecap="round" />
            </svg>
          </motion.div>
          <span className="sidebar__logo-text">Nexus</span>
        </div>

        {/* Navigation */}
        <nav className="sidebar__nav">
          {filtered.map((item) => {
            const isActive = item.end
              ? location.pathname === item.to
              : location.pathname.startsWith(item.to)
            return (
              <NavLink
                key={item.to}
                to={item.to}
                className={`sidebar__link ${isActive ? 'sidebar__link--active' : ''}`}
                onClick={() => setCollapsed(false)}
              >
                <item.icon className="sidebar__link-icon" />
                <span className="sidebar__link-label">{item.label}</span>
                <AnimatePresence>
                  {isActive && (
                    <motion.div
                      className="sidebar__link-indicator"
                      layoutId="activeIndicator"
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      exit={{ opacity: 0 }}
                      transition={{ type: 'spring', stiffness: 500, damping: 35 }}
                    />
                  )}
                </AnimatePresence>
              </NavLink>
            )
          })}
        </nav>

        {/* User section */}
        <div className="sidebar__footer">
          <div className="sidebar__user">
            <div className="sidebar__avatar">
              {user?.full_name?.charAt(0) || user?.email?.charAt(0) || '?'}
            </div>
            <div className="sidebar__user-info">
              <span className="sidebar__user-name">
                {user?.full_name || user?.email}
              </span>
              <span className="sidebar__user-role">
                {user?.roles?.join(', ')}
              </span>
            </div>
          </div>
          <motion.button
            className="sidebar__logout"
            onClick={logout}
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            title="Sign out"
          >
            <HiOutlineArrowRightOnRectangle />
          </motion.button>
        </div>
      </motion.aside>
    </>
  )
}
