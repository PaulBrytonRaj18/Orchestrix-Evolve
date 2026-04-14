import React from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import '../component.css'

const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.05,
      delayChildren: 0.1
    }
  }
}

const itemVariants = {
  hidden: { opacity: 0, x: -20 },
  visible: {
    opacity: 1,
    x: 0,
    transition: {
      type: "spring",
      stiffness: 100,
      damping: 12
    }
  }
}

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

  return (
    <div className="session-sidebar">
      {/* Header */}
      <div className="sidebar-header">
        <div className="sidebar-header-icon">
          <span>📂</span>
          <motion.div 
            className="icon-glow"
            animate={{
              opacity: [0.5, 1, 0.5],
              scale: [1, 1.2, 1]
            }}
            transition={{
              duration: 2,
              repeat: Infinity,
              ease: "easeInOut"
            }}
          />
        </div>
        <div className="sidebar-header-content">
          <h3 className="sidebar-title">Research Sessions</h3>
          <p className="sidebar-subtitle">{sessions.length} sessions</p>
        </div>
      </div>

      {/* Divider */}
      <div className="sidebar-divider">
        <motion.div 
          className="divider-glow"
          animate={{
            backgroundPosition: ['0% 50%', '100% 50%', '0% 50%']
          }}
          transition={{
            duration: 3,
            repeat: Infinity,
            ease: "linear"
          }}
        />
      </div>

      {/* Sessions List */}
      <div className="sessions-list">
        <AnimatePresence>
          {sessions.length === 0 ? (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="empty-sessions"
            >
              <motion.div
                className="empty-icon"
                animate={{
                  y: [0, -5, 0],
                  opacity: [0.5, 1, 0.5]
                }}
                transition={{
                  duration: 2,
                  repeat: Infinity,
                  ease: "easeInOut"
                }}
              >
                🔍
              </motion.div>
              <p>No sessions yet</p>
              <span>Start a new search to begin</span>
            </motion.div>
          ) : (
            <motion.div
              variants={containerVariants}
              initial="hidden"
              animate="visible"
              className="sessions-container"
            >
              {sessions.map((session, index) => (
                <motion.button
                  key={session.id}
                  variants={itemVariants}
                  onClick={() => onSelectSession(session.id)}
                  className={`session-card ${currentSessionId === session.id ? 'active' : ''}`}
                  whileHover={{ 
                    scale: 1.02,
                    x: 4
                  }}
                  whileTap={{ scale: 0.98 }}
                >
                  {/* Active indicator */}
                  {currentSessionId === session.id && (
                    <motion.div
                      className="active-indicator"
                      layoutId="activeSession"
                      transition={{ type: "spring", stiffness: 500, damping: 30 }}
                    />
                  )}
                  
                  {/* Card glow effect */}
                  <div className="card-glow" />
                  
                  {/* Card content */}
                  <div className="card-content">
                    <div className="card-header">
                      <span className="card-icon">📄</span>
                      <span className="card-time">{formatRelativeTime(session.created_at)}</span>
                    </div>
                    
                    <h4 className="card-title">{session.name}</h4>
                    
                    <p className="card-query">{session.query}</p>
                    
                    <div className="card-footer">
                      <div className="paper-count">
                        <span className="count-icon">📑</span>
                        <span className="count-number">{session.paper_count || 0}</span>
                        <span className="count-label">papers</span>
                      </div>
                      
                      <motion.div 
                        className="card-arrow"
                        animate={currentSessionId === session.id ? {
                          x: [0, 4, 0]
                        } : {}}
                        transition={{
                          duration: 1,
                          repeat: Infinity,
                          ease: "easeInOut"
                        }}
                      >
                        →
                      </motion.div>
                    </div>
                  </div>
                </motion.button>
              ))}
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Bottom decoration */}
      <div className="sidebar-bottom-glow" />
    </div>
  )
}

export default SessionSidebar
