import React, { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { api } from '../api.js'
import { AlertTriangle, Check, X, Loader2, Shield } from 'lucide-react'

function ConflictsPanel({ sessionId }) {
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
    } catch (error) {
      console.error('Error resolving conflict:', error)
    } finally {
      setIsResolving(false)
    }
  }

  const handleDetectConflicts = async () => {
    setIsLoading(true)
    try {
      const result = await api.detectConflicts(sessionId)
      setConflicts(result.conflicts || [])
    } catch (error) {
      console.error('Error detecting conflicts:', error)
    } finally {
      setIsLoading(false)
    }
  }

  const getSeverityBadge = (severity) => {
    switch (severity) {
      case 'high':
        return { class: 'badge-error', label: 'High' }
      case 'medium':
        return { class: 'badge-warning', label: 'Medium' }
      default:
        return { class: 'badge-default', label: 'Low' }
    }
  }

  const unresolvedConflicts = conflicts.filter(c => !c.resolved)
  const resolvedConflicts = conflicts.filter(c => c.resolved)

  if (isLoading && conflicts.length === 0) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 'var(--space-16)' }}>
        <Loader2 size={24} style={{ animation: 'spin 0.8s linear infinite', color: 'var(--text-tertiary)' }} />
      </div>
    )
  }

  return (
    <div>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 'var(--space-6)' }}>
        <div style={{ display: 'flex', gap: 'var(--space-4)' }}>
          <div className="stat-card" style={{ padding: 'var(--space-3) var(--space-4)', minWidth: '100px' }}>
            <div style={{ fontSize: 'var(--text-2xl)', fontWeight: 'var(--font-bold)' }}>{unresolvedConflicts.length}</div>
            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-tertiary)' }}>Unresolved</div>
          </div>
          <div className="stat-card" style={{ padding: 'var(--space-3) var(--space-4)', minWidth: '100px' }}>
            <div style={{ fontSize: 'var(--text-2xl)', fontWeight: 'var(--font-bold)' }}>{resolvedConflicts.length}</div>
            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-tertiary)' }}>Resolved</div>
          </div>
        </div>
        <button
          className="btn btn-secondary"
          onClick={handleDetectConflicts}
          disabled={isLoading}
        >
          {isLoading ? <Loader2 size={14} style={{ animation: 'spin 0.8s linear infinite' }} /> : <AlertTriangle size={14} />}
          Detect Conflicts
        </button>
      </div>

      {/* Unresolved Conflicts */}
      {unresolvedConflicts.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)', marginBottom: 'var(--space-6)' }}>
          {unresolvedConflicts.map((conflict) => {
            const badge = getSeverityBadge(conflict.severity)
            return (
              <div key={conflict.id} className="card" style={{ padding: 'var(--space-5)' }}>
                <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 'var(--space-3)' }}>
                  <div style={{ display: 'flex', alignItems: 'flex-start', gap: 'var(--space-3)' }}>
                    <div style={{ 
                      width: '32px', 
                      height: '32px', 
                      borderRadius: 'var(--radius-md)', 
                      background: 'var(--error-subtle)',
                      color: 'var(--error-primary)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      flexShrink: 0
                    }}>
                      <AlertTriangle size={16} />
                    </div>
                    <div>
                      <h4 style={{ fontSize: 'var(--text-sm)', fontWeight: 'var(--font-semibold)', marginBottom: 'var(--space-1)' }}>
                        {conflict.title}
                      </h4>
                      <span className={`badge ${badge.class}`}>{badge.label}</span>
                    </div>
                  </div>
                </div>
                
                {conflict.description && (
                  <p style={{ fontSize: 'var(--text-sm)', color: 'var(--text-secondary)', marginBottom: 'var(--space-3)', marginLeft: '44px' }}>
                    {conflict.description}
                  </p>
                )}

                <div style={{ display: 'flex', gap: 'var(--space-2)', marginLeft: '44px' }}>
                  <button
                    className="btn btn-primary btn-sm"
                    onClick={() => setSelectedConflict(conflict)}
                  >
                    <Check size={14} />
                    Resolve
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* Resolved Conflicts */}
      {resolvedConflicts.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
          <h4 style={{ fontSize: 'var(--text-sm)', fontWeight: 'var(--font-semibold)', color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Resolved
          </h4>
          {resolvedConflicts.map((conflict) => (
            <div key={conflict.id} className="card" style={{ padding: 'var(--space-4)', opacity: 0.7 }}>
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: 'var(--space-3)' }}>
                <div style={{ 
                  width: '24px', 
                  height: '24px', 
                  borderRadius: 'var(--radius-full)', 
                  background: 'var(--success-subtle)',
                  color: 'var(--success-primary)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0
                }}>
                  <Check size={12} />
                </div>
                <div>
                  <h4 style={{ fontSize: 'var(--text-sm)', fontWeight: 'var(--font-medium)', marginBottom: 'var(--space-1)' }}>
                    {conflict.title}
                  </h4>
                  {conflict.resolution_notes && (
                    <p style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>
                      {conflict.resolution_notes}
                    </p>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Empty State */}
      {conflicts.length === 0 && !isLoading && (
        <div className="empty-state">
          <div className="empty-icon">
            <Shield size={32} strokeWidth={1} />
          </div>
          <h3 className="empty-title">No conflicts detected</h3>
          <p className="empty-description">
            Click "Detect Conflicts" to analyze papers for contradictions
          </p>
        </div>
      )}

      {/* Resolution Modal */}
      <AnimatePresence>
        {selectedConflict && (
          <motion.div
            className="modal-backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setSelectedConflict(null)}
          >
            <motion.div
              className="modal"
              initial={{ opacity: 0, scale: 0.95, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 20 }}
              onClick={(e) => e.stopPropagation()}
            >
              <div className="modal-header">
                <h3 className="modal-title">Resolve Conflict</h3>
                <button className="btn btn-ghost btn-icon" onClick={() => setSelectedConflict(null)}>
                  <X size={18} />
                </button>
              </div>
              <div className="modal-body">
                <div style={{ marginBottom: 'var(--space-4)' }}>
                  <h4 style={{ fontSize: 'var(--text-sm)', fontWeight: 'var(--font-semibold)', marginBottom: 'var(--space-2)' }}>
                    {selectedConflict.title}
                  </h4>
                  {selectedConflict.description && (
                    <p style={{ fontSize: 'var(--text-sm)', color: 'var(--text-secondary)' }}>
                      {selectedConflict.description}
                    </p>
                  )}
                </div>
                <div className="form-group">
                  <label className="form-label">Resolution Notes</label>
                  <textarea
                    className="form-input"
                    placeholder="Explain how this conflict was resolved..."
                    value={resolutionText}
                    onChange={(e) => setResolutionText(e.target.value)}
                    rows={4}
                    style={{ minHeight: '100px', resize: 'vertical' }}
                  />
                </div>
              </div>
              <div className="modal-footer">
                <button className="btn btn-secondary" onClick={() => setSelectedConflict(null)}>
                  Cancel
                </button>
                <button
                  className="btn btn-primary"
                  disabled={!resolutionText.trim() || isResolving}
                  onClick={() => handleResolve(selectedConflict.id)}
                >
                  {isResolving ? 'Resolving...' : 'Resolve Conflict'}
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

export default ConflictsPanel
