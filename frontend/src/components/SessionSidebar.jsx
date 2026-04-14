import React from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { FileText, Clock } from 'lucide-react'

function SessionSidebar({ sessions, currentSessionId, onSelectSession }) {
  const formatRelativeTime = (dateString) => {
    const date = new Date(dateString)
    const now = new Date()
    const diffMs = now - date
    const diffMins = Math.floor(diffMs / 60000)
    const diffHours = Math.floor(diffMs / 3600000)
    const diffDays = Math.floor(diffMs / 86400000)

    if (diffMins < 1) return 'Just now'
    if (diffMins < 60) return `${diffMins}m ago`
    if (diffHours < 24) return `${diffHours}h ago`
    if (diffDays < 7) return `${diffDays}d ago`
    return date.toLocaleDateString()
  }

  if (sessions.length === 0) {
    return (
      <div style={{ 
        padding: 'var(--space-4)', 
        textAlign: 'center', 
        color: 'var(--text-tertiary)',
        fontSize: 'var(--text-sm)'
      }}>
        No sessions yet
      </div>
    )
  }

  return (
    <div className="sidebar-list">
      {sessions.map((session) => {
        const isActive = currentSessionId === session.id
        return (
          <motion.button
            key={session.id}
            onClick={() => onSelectSession(session.id)}
            className={`sidebar-item ${isActive ? 'active' : ''}`}
            whileHover={{ scale: 1.01 }}
            whileTap={{ scale: 0.99 }}
            style={{ width: '100%', textAlign: 'left' }}
          >
            <div className="sidebar-item-icon" style={{ background: isActive ? 'var(--accent-primary)' : 'var(--bg-tertiary)' }}>
              <FileText size={14} style={{ color: isActive ? 'white' : 'var(--text-tertiary)' }} />
            </div>
            <div className="sidebar-item-content">
              <div className="sidebar-item-title" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '140px' }}>
                  {session.name}
                </span>
              </div>
              <div className="sidebar-item-meta" style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <Clock size={10} />
                  {formatRelativeTime(session.created_at)}
                </span>
                <span>•</span>
                <span>{session.paper_count || 0} papers</span>
              </div>
            </div>
          </motion.button>
        )
      })}
    </div>
  )
}

export default SessionSidebar
