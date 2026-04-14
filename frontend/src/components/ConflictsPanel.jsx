import React, { useState, useEffect } from 'react'
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
  hidden: { opacity: 0, y: 20 },
  visible: {
    opacity: 1,
    y: 0,
    transition: {
      type: "spring",
      stiffness: 100,
      damping: 12
    }
  }
}

const pulseVariants = {
  pulse: {
    boxShadow: [
      "0 0 20px rgba(220, 38, 38, 0.3)",
      "0 0 40px rgba(220, 38, 38, 0.6)",
      "0 0 20px rgba(220, 38, 38, 0.3)"
    ],
    transition: {
      duration: 2,
      repeat: Infinity,
      ease: "easeInOut"
    }
  }
}

function ConflictsPanel({ sessionId, onConflictResolved }) {
  const [conflicts, setConflicts] = useState([])
  const [isLoading, setIsLoading] = useState(false)
  const [selectedConflict, setSelectedConflict] = useState(null)
  const [resolutionText, setResolutionText] = useState('')
  const [isResolving, setIsResolving] = useState(false)

  useEffect(() => {
    if (sessionId) {
      loadConflicts()
    }
  }, [sessionId])

  const loadConflicts = async () => {
    setIsLoading(true)
    try {
      const { api } = await import('../api.js')
      const data = await api.getConflicts(sessionId)
      setConflicts(data)
    } catch (error) {
      console.error('Error loading conflicts:', error)
    } finally {
      setIsLoading(false)
    }
  }

  const handleResolve = async (conflictId) => {
    if (!resolutionText.trim()) return
    
    setIsResolving(true)
    try {
      const { api } = await import('../api.js')
      await api.resolveConflict(sessionId, conflictId, resolutionText)
      setConflicts(prev =>
        prev.map(c =>
          c.id === conflictId
            ? { ...c, resolved: true, resolution_notes: resolutionText }
            : c
        )
      )
      setSelectedConflict(null)
      setResolutionText('')
      if (onConflictResolved) onConflictResolved()
    } catch (error) {
      console.error('Error resolving conflict:', error)
      alert('Error resolving conflict: ' + error.message)
    } finally {
      setIsResolving(false)
    }
  }

  const handleDetectConflicts = async () => {
    setIsLoading(true)
    try {
      const { api } = await import('../api.js')
      const result = await api.detectConflicts(sessionId)
      setConflicts(result.conflicts || [])
      if (result.summary) {
        alert(result.summary)
      }
    } catch (error) {
      console.error('Error detecting conflicts:', error)
      alert('Error detecting conflicts: ' + error.message)
    } finally {
      setIsLoading(false)
    }
  }

  const getSeverityColor = (severity) => {
    switch (severity) {
      case 'high': return 'severity-high'
      case 'medium': return 'severity-medium'
      case 'low': return 'severity-low'
      default: return 'severity-medium'
    }
  }

  const getConflictIcon = (type) => {
    switch (type) {
      case 'methodology_conflict': return '🔬'
      case 'finding_conflict': return '📊'
      case 'conclusion_conflict': return '📝'
      case 'data_conflict': return '📈'
      default: return '⚠️'
    }
  }

  const unresolvedConflicts = conflicts.filter(c => !c.resolved)
  const resolvedConflicts = conflicts.filter(c => c.resolved)

  return (
    <div className="conflicts-panel">
      {/* Header Actions */}
      <motion.div 
        className="conflicts-header"
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <div className="conflicts-stats">
          <motion.div 
            className="stat-card unresolved"
            whileHover={{ scale: 1.02 }}
          >
            <span className="stat-icon">⚠️</span>
            <span className="stat-number">{unresolvedConflicts.length}</span>
            <span className="stat-label">Unresolved</span>
          </motion.div>
          <motion.div 
            className="stat-card resolved"
            whileHover={{ scale: 1.02 }}
          >
            <span className="stat-icon">✓</span>
            <span className="stat-number">{resolvedConflicts.length}</span>
            <span className="stat-label">Resolved</span>
          </motion.div>
        </div>

        <motion.button
          className="detect-conflicts-btn"
          onClick={handleDetectConflicts}
          disabled={isLoading}
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
        >
          <span className="btn-icon">🔍</span>
          <span>Detect Conflicts</span>
        </motion.button>
      </motion.div>

      {/* Loading State */}
      {isLoading && (
        <motion.div
          className="conflicts-loading"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
        >
          <motion.div 
            className="loading-spinner"
            variants={pulseVariants}
            animate="pulse"
          />
          <p>Analyzing conflicts...</p>
        </motion.div>
      )}

      {/* Unresolved Conflicts */}
      {unresolvedConflicts.length > 0 && (
        <motion.div 
          className="conflicts-section"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
        >
          <h3 className="section-title">
            <span className="title-icon">⚠️</span>
            Unresolved Conflicts
          </h3>
          
          <motion.div 
            className="conflicts-list"
            variants={containerVariants}
            initial="hidden"
            animate="visible"
          >
            {unresolvedConflicts.map((conflict, index) => (
              <motion.div
                key={conflict.id}
                variants={itemVariants}
                className={`conflict-card ${getSeverityColor(conflict.severity)}`}
                whileHover={{ scale: 1.01, y: -2 }}
              >
                <div className="conflict-glow" />
                
                <div className="conflict-header">
                  <motion.div 
                    className="conflict-icon"
                    animate={{ 
                      rotate: [0, 10, -10, 0],
                      scale: [1, 1.1, 1]
                    }}
                    transition={{ duration: 2, repeat: Infinity }}
                  >
                    {getConflictIcon(conflict.conflict_type)}
                  </motion.div>
                  
                  <div className="conflict-info">
                    <h4 className="conflict-title">{conflict.title}</h4>
                    <span className={`severity-badge ${getSeverityColor(conflict.severity)}`}>
                      {conflict.severity}
                    </span>
                  </div>
                </div>

                {conflict.description && (
                  <p className="conflict-description">{conflict.description}</p>
                )}

                <div className="conflict-insights">
                  {conflict.analysis_insight && (
                    <div className="insight-box analysis">
                      <span className="insight-icon">📊</span>
                      <span className="insight-label">Analysis:</span>
                      <p>{conflict.analysis_insight}</p>
                    </div>
                  )}
                  {conflict.summarization_insight && (
                    <div className="insight-box summarization">
                      <span className="insight-icon">📝</span>
                      <span className="insight-label">Summary:</span>
                      <p>{conflict.summarization_insight}</p>
                    </div>
                  )}
                </div>

                <div className="conflict-actions">
                  <motion.button
                    className="resolve-btn"
                    onClick={() => setSelectedConflict(conflict)}
                    whileHover={{ scale: 1.05 }}
                    whileTap={{ scale: 0.95 }}
                  >
                    <span className="btn-icon">✓</span>
                    <span>Resolve</span>
                  </motion.button>
                </div>
              </motion.div>
            ))}
          </motion.div>
        </motion.div>
      )}

      {/* Resolved Conflicts */}
      {resolvedConflicts.length > 0 && (
        <motion.div 
          className="conflicts-section resolved-section"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.2 }}
        >
          <h3 className="section-title">
            <span className="title-icon">✓</span>
            Resolved Conflicts
          </h3>
          
          <motion.div 
            className="conflicts-list"
            variants={containerVariants}
            initial="hidden"
            animate="visible"
          >
            {resolvedConflicts.map((conflict, index) => (
              <motion.div
                key={conflict.id}
                variants={itemVariants}
                className="conflict-card resolved"
                whileHover={{ scale: 1.01 }}
              >
                <div className="conflict-header">
                  <div className="conflict-icon resolved">✓</div>
                  <div className="conflict-info">
                    <h4 className="conflict-title">{conflict.title}</h4>
                    <span className="resolved-badge">Resolved</span>
                  </div>
                </div>
                
                {conflict.resolution_notes && (
                  <div className="resolution-notes">
                    <span className="resolution-icon">📝</span>
                    <p>{conflict.resolution_notes}</p>
                  </div>
                )}
              </motion.div>
            ))}
          </motion.div>
        </motion.div>
      )}

      {/* Empty State */}
      {conflicts.length === 0 && !isLoading && (
        <motion.div
          className="conflicts-empty"
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
        >
          <motion.div 
            className="empty-glow"
            animate={{
              scale: [1, 1.3, 1],
              opacity: [0.3, 0.6, 0.3]
            }}
            transition={{ duration: 3, repeat: Infinity }}
          />
          <motion.div
            className="empty-icon"
            animate={{ y: [0, -10, 0] }}
            transition={{ duration: 2, repeat: Infinity }}
          >
            🛡️
          </motion.div>
          <h3 className="empty-title">No Conflicts Detected</h3>
          <p className="empty-subtitle">
            Click "Detect Conflicts" to analyze papers for conflicts
          </p>
        </motion.div>
      )}

      {/* Resolution Modal */}
      <AnimatePresence>
        {selectedConflict && (
          <motion.div
            className="modal-overlay"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setSelectedConflict(null)}
          >
            <motion.div
              className="resolution-modal"
              initial={{ opacity: 0, scale: 0.9, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.9, y: 20 }}
              onClick={(e) => e.stopPropagation()}
            >
              <div className="modal-glow" />
              
              <div className="modal-header">
                <h3 className="modal-title">
                  <span className="modal-icon">✓</span>
                  Resolve Conflict
                </h3>
                <motion.button
                  className="modal-close"
                  onClick={() => setSelectedConflict(null)}
                  whileHover={{ scale: 1.1, rotate: 90 }}
                  whileTap={{ scale: 0.9 }}
                >
                  ✕
                </motion.button>
              </div>

              <div className="modal-content">
                <div className="conflict-preview">
                  <h4>{selectedConflict.title}</h4>
                  <p>{selectedConflict.description}</p>
                </div>

                <div className="resolution-input">
                  <label className="input-label">
                    <span className="label-icon">📝</span>
                    Resolution Notes
                  </label>
                  <textarea
                    className="resolution-textarea"
                    placeholder="Explain how this conflict was resolved..."
                    value={resolutionText}
                    onChange={(e) => setResolutionText(e.target.value)}
                    rows={4}
                  />
                </div>

                <div className="modal-actions">
                  <motion.button
                    className="cancel-btn"
                    onClick={() => setSelectedConflict(null)}
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                  >
                    Cancel
                  </motion.button>
                  <motion.button
                    className="confirm-resolve-btn"
                    onClick={() => handleResolve(selectedConflict.id)}
                    disabled={!resolutionText.trim() || isResolving}
                    whileHover={resolutionText.trim() ? { scale: 1.02 } : {}}
                    whileTap={resolutionText.trim() ? { scale: 0.98 } : {}}
                  >
                    <span className="btn-icon">✓</span>
                    <span>{isResolving ? 'Resolving...' : 'Resolve Conflict'}</span>
                  </motion.button>
                </div>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

export default ConflictsPanel