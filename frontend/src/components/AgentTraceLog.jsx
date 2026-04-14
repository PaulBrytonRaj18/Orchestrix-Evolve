import React from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import '../component.css'

const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.1,
      delayChildren: 0.1
    }
  }
}

const itemVariants = {
  hidden: { opacity: 0, x: -20, scale: 0.95 },
  visible: {
    opacity: 1,
    x: 0,
    scale: 1,
    transition: {
      type: "spring",
      stiffness: 100,
      damping: 12
    }
  }
}

const pulseVariants = {
  pulse: {
    scale: [1, 1.2, 1],
    opacity: [0.7, 1, 0.7],
    transition: {
      duration: 1.5,
      repeat: Infinity,
      ease: "easeInOut"
    }
  }
}

const spinVariants = {
  spin: {
    rotate: 360,
    transition: {
      duration: 1,
      repeat: Infinity,
      ease: "linear"
    }
  }
}

function AgentTraceLog({ trace }) {
  if (!trace || trace.length === 0) {
    return (
      <motion.div
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        className="trace-empty"
      >
        <motion.div
          variants={pulseVariants}
          animate="pulse"
          className="trace-empty-icon"
        >
          🤖
        </motion.div>
        <p>No agent activity yet...</p>
        <span className="trace-empty-hint">Agents will appear here as they work</span>
      </motion.div>
    )
  }

  const getStatusConfig = (status) => {
    switch (status) {
      case 'done':
        return {
          icon: '✓',
          className: 'status-done',
          label: 'Completed'
        }
      case 'running':
        return {
          icon: '⟳',
          className: 'status-running',
          label: 'Running'
        }
      case 'error':
        return {
          icon: '✕',
          className: 'status-error',
          label: 'Error'
        }
      case 'skipped':
      default:
        return {
          icon: '○',
          className: 'status-skipped',
          label: 'Skipped'
        }
    }
  }

  return (
    <div className="trace-container">
      <motion.div 
        className="trace-glow"
        animate={{
          opacity: [0.3, 0.5, 0.3]
        }}
        transition={{
          duration: 4,
          repeat: Infinity,
          ease: "easeInOut"
        }}
      />
      
      <div className="trace-header">
        <motion.span 
          className="trace-header-icon"
          animate={{
            rotate: [0, 10, -10, 0]
          }}
          transition={{
            duration: 2,
            repeat: Infinity,
            ease: "easeInOut"
          }}
        >
          🔬
        </motion.span>
        <h3 className="trace-title">Agent Activity</h3>
        <div className="trace-count">
          <motion.span
            key={trace.length}
            initial={{ scale: 1.5, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ type: "spring", stiffness: 500 }}
          >
            {trace.length}
          </motion.span>
        </div>
      </div>

      <motion.div
        className="trace-timeline"
        variants={containerVariants}
        initial="hidden"
        animate="visible"
      >
        <div className="timeline-line" />
        
        <AnimatePresence>
          {trace.map((entry, index) => {
            const statusConfig = getStatusConfig(entry.status)
            
            return (
              <motion.div
                key={index}
                variants={itemVariants}
                className={`trace-entry ${statusConfig.className}`}
                whileHover={{ 
                  scale: 1.02, 
                  x: 4,
                  transition: { type: "spring", stiffness: 300 }
                }}
                layout
              >
                <div className="entry-connector">
                  <motion.div 
                    className={`entry-dot ${statusConfig.className}`}
                    animate={entry.status === 'running' ? {
                      boxShadow: [
                        "0 0 10px rgba(220, 38, 38, 0.5)",
                        "0 0 25px rgba(220, 38, 38, 0.8)",
                        "0 0 10px rgba(220, 38, 38, 0.5)"
                      ]
                    } : {}}
                    transition={{
                      duration: 1.5,
                      repeat: Infinity,
                      ease: "easeInOut"
                    }}
                  />
                </div>

                <div className="entry-content">
                  <div className="entry-header">
                    <motion.div 
                      className={`entry-icon ${statusConfig.className}`}
                      variants={entry.status === 'running' ? spinVariants : {}}
                      animate={entry.status === 'running' ? 'spin' : {}}
                    >
                      {statusConfig.icon}
                    </motion.div>
                    
                    <div className="entry-info">
                      <span className="entry-agent">{entry.agent}</span>
                      <span className={`entry-status-badge ${statusConfig.className}`}>
                        {statusConfig.label}
                      </span>
                    </div>

                    {entry.status === 'running' && (
                      <motion.div 
                        className="entry-progress"
                        initial={{ width: "0%" }}
                        animate={{ width: "100%" }}
                        transition={{ 
                          duration: 3, 
                          repeat: Infinity,
                          ease: "linear"
                        }}
                      />
                    )}
                  </div>

                  <div className="entry-body">
                    {entry.status === 'running' && (
                      <motion.span
                        className="entry-message running"
                        animate={{ opacity: [0.5, 1, 0.5] }}
                        transition={{ duration: 1.5, repeat: Infinity }}
                      >
                        Processing...
                      </motion.span>
                    )}
                    {entry.status === 'done' && entry.result && (
                      <span className="entry-message done">{entry.result}</span>
                    )}
                    {entry.status === 'skipped' && entry.reason && (
                      <span className="entry-message skipped">{entry.reason}</span>
                    )}
                    {entry.status === 'error' && entry.error && (
                      <span className="entry-message error">{entry.error}</span>
                    )}
                  </div>

                  {entry.duration && (
                    <div className="entry-footer">
                      <span className="entry-duration">
                        ⏱ {entry.duration}ms
                      </span>
                    </div>
                  )}
                </div>

                <motion.div 
                  className="entry-glow"
                  initial={{ opacity: 0 }}
                  whileHover={{ opacity: 1 }}
                />
              </motion.div>
            )
          })}
        </AnimatePresence>
      </motion.div>
    </div>
  )
}

export default AgentTraceLog
