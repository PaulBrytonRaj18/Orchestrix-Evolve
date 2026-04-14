import React, { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import '../component.css'

const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.08,
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
    opacity: [0.5, 1, 0.5],
    transition: {
      duration: 1.5,
      repeat: Infinity,
      ease: "easeInOut"
    }
  }
}

function DigestManagement() {
  const [digests, setDigests] = useState([])
  const [isLoading, setIsLoading] = useState(false)
  const [showCreateForm, setShowCreateForm] = useState(false)
  const [selectedDigest, setSelectedDigest] = useState(null)
  const [digestRuns, setDigestRuns] = useState(null)
  const [formData, setFormData] = useState({
    name: '',
    query: '',
    frequency: 'weekly',
    notify_email: ''
  })
  const [isCreating, setIsCreating] = useState(false)

  useEffect(() => {
    loadDigests()
  }, [])

  const loadDigests = async () => {
    setIsLoading(true)
    try {
      const { api } = await import('../api.js')
      const data = await api.getDigests()
      setDigests(data)
    } catch (error) {
      console.error('Error loading digests:', error)
    } finally {
      setIsLoading(false)
    }
  }

  const handleCreateDigest = async (e) => {
    e.preventDefault()
    if (!formData.name.trim() || !formData.query.trim()) return

    setIsCreating(true)
    try {
      const { api } = await import('../api.js')
      await api.createDigest(
        formData.name,
        formData.query,
        formData.frequency,
        formData.notify_email || null
      )
      setFormData({ name: '', query: '', frequency: 'weekly', notify_email: '' })
      setShowCreateForm(false)
      loadDigests()
    } catch (error) {
      console.error('Error creating digest:', error)
      alert('Error creating digest: ' + error.message)
    } finally {
      setIsCreating(false)
    }
  }

  const handleToggleDigest = async (digestId) => {
    try {
      const { api } = await import('../api.js')
      const result = await api.toggleDigest(digestId)
      setDigests(prev =>
        prev.map(d =>
          d.id === digestId ? { ...d, is_active: result.is_active } : d
        )
      )
    } catch (error) {
      console.error('Error toggling digest:', error)
    }
  }

  const handleDeleteDigest = async (digestId) => {
    if (!confirm('Are you sure you want to delete this digest?')) return

    try {
      const { api } = await import('../api.js')
      await api.deleteDigest(digestId)
      setDigests(prev => prev.filter(d => d.id !== digestId))
      if (selectedDigest?.id === digestId) {
        setSelectedDigest(null)
        setDigestRuns(null)
      }
    } catch (error) {
      console.error('Error deleting digest:', error)
    }
  }

  const handleTriggerRun = async (digestId) => {
    try {
      const { api } = await import('../api.js')
      await api.triggerDigestRun(digestId)
      alert('Digest run triggered!')
    } catch (error) {
      console.error('Error triggering digest:', error)
    }
  }

  const handleViewDigest = async (digestId) => {
    try {
      const { api } = await import('../api.js')
      const data = await api.getDigest(digestId)
      setSelectedDigest(data)
      setDigestRuns(data.runs || [])
    } catch (error) {
      console.error('Error loading digest details:', error)
    }
  }

  const formatDate = (dateString) => {
    if (!dateString) return 'Never'
    return new Date(dateString).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  const getFrequencyLabel = (freq) => {
    const labels = {
      daily: 'Daily',
      weekly: 'Weekly',
      biweekly: 'Biweekly',
      monthly: 'Monthly'
    }
    return labels[freq] || freq
  }

  const getStatusColor = (isActive) => isActive ? 'active' : 'inactive'

  return (
    <div className="digest-container">
      {/* Header */}
      <motion.div
        className="digest-header"
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <motion.div 
          className="header-glow"
          animate={{
            scale: [1, 1.1, 1],
            opacity: [0.4, 0.7, 0.4]
          }}
          transition={{ duration: 3, repeat: Infinity }}
        />
        <div className="header-content">
          <motion.div
            className="header-icon"
            animate={{ rotateY: [0, 360] }}
            transition={{ duration: 8, repeat: Infinity, ease: "linear" }}
          >
            📬
          </motion.div>
          <div>
            <h1 className="header-title">Scheduled Digests</h1>
            <p className="header-subtitle">Automate your research updates</p>
          </div>
        </div>
        <motion.button
          className="create-digest-btn"
          onClick={() => setShowCreateForm(true)}
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
        >
          <span className="btn-icon">+</span>
          <span>New Digest</span>
        </motion.button>
      </motion.div>

      {/* Create Form Modal */}
      <AnimatePresence>
        {showCreateForm && (
          <motion.div
            className="modal-overlay"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setShowCreateForm(false)}
          >
            <motion.div
              className="digest-form-modal"
              initial={{ opacity: 0, scale: 0.9, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.9, y: 20 }}
              onClick={(e) => e.stopPropagation()}
            >
              <div className="modal-glow" />
              
              <div className="modal-header">
                <h3 className="modal-title">
                  <span className="modal-icon">📬</span>
                  Create Scheduled Digest
                </h3>
                <motion.button
                  className="modal-close"
                  onClick={() => setShowCreateForm(false)}
                  whileHover={{ scale: 1.1, rotate: 90 }}
                  whileTap={{ scale: 0.9 }}
                >
                  ✕
                </motion.button>
              </div>

              <form onSubmit={handleCreateDigest} className="digest-form">
                <div className="form-group">
                  <label className="form-label">
                    <span className="label-icon">📛</span>
                    Digest Name
                  </label>
                  <input
                    type="text"
                    className="form-input"
                    placeholder="e.g., ML Papers Weekly"
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    required
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">
                    <span className="label-icon">🔍</span>
                    Search Query
                  </label>
                  <input
                    type="text"
                    className="form-input"
                    placeholder="e.g., machine learning transformers"
                    value={formData.query}
                    onChange={(e) => setFormData({ ...formData, query: e.target.value })}
                    required
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">
                    <span className="label-icon">📅</span>
                    Frequency
                  </label>
                  <select
                    className="form-select"
                    value={formData.frequency}
                    onChange={(e) => setFormData({ ...formData, frequency: e.target.value })}
                  >
                    <option value="daily">Daily</option>
                    <option value="weekly">Weekly</option>
                    <option value="biweekly">Biweekly</option>
                    <option value="monthly">Monthly</option>
                  </select>
                </div>

                <div className="form-group">
                  <label className="form-label">
                    <span className="label-icon">📧</span>
                    Notification Email (optional)
                  </label>
                  <input
                    type="email"
                    className="form-input"
                    placeholder="your@email.com"
                    value={formData.notify_email}
                    onChange={(e) => setFormData({ ...formData, notify_email: e.target.value })}
                  />
                </div>

                <div className="form-actions">
                  <motion.button
                    type="button"
                    className="cancel-btn"
                    onClick={() => setShowCreateForm(false)}
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                  >
                    Cancel
                  </motion.button>
                  <motion.button
                    type="submit"
                    className="submit-btn"
                    disabled={isCreating || !formData.name.trim() || !formData.query.trim()}
                    whileHover={formData.name.trim() && formData.query.trim() ? { scale: 1.02 } : {}}
                    whileTap={formData.name.trim() && formData.query.trim() ? { scale: 0.98 } : {}}
                  >
                    <span className="btn-icon">✓</span>
                    <span>{isCreating ? 'Creating...' : 'Create Digest'}</span>
                  </motion.button>
                </div>
              </form>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Digest List */}
      <div className="digest-content">
        <motion.div 
          className="digests-grid"
          variants={containerVariants}
          initial="hidden"
          animate="visible"
        >
          {digests.length === 0 && !isLoading ? (
            <motion.div
              className="empty-digests"
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
                📬
              </motion.div>
              <h3>No Scheduled Digests</h3>
              <p>Create a digest to get automatic research updates</p>
            </motion.div>
          ) : (
            digests.map((digest, index) => (
              <motion.div
                key={digest.id}
                variants={itemVariants}
                className={`digest-card ${getStatusColor(digest.is_active)}`}
                whileHover={{ scale: 1.02, y: -4 }}
                onClick={() => handleViewDigest(digest.id)}
              >
                <div className="card-glow" />
                
                <div className="digest-card-header">
                  <div className="digest-info">
                    <h3 className="digest-name">{digest.name}</h3>
                    <p className="digest-query">
                      <span className="query-icon">🔍</span>
                      {digest.query}
                    </p>
                  </div>
                  <div className={`status-badge ${getStatusColor(digest.is_active)}`}>
                    {digest.is_active ? 'Active' : 'Paused'}
                  </div>
                </div>

                <div className="digest-meta">
                  <div className="meta-item">
                    <span className="meta-icon">📅</span>
                    <span className="meta-label">Frequency:</span>
                    <span className="meta-value">{getFrequencyLabel(digest.frequency)}</span>
                  </div>
                  <div className="meta-item">
                    <span className="meta-icon">⏰</span>
                    <span className="meta-label">Next run:</span>
                    <span className="meta-value">{formatDate(digest.next_run_at)}</span>
                  </div>
                  {digest.last_run_at && (
                    <div className="meta-item">
                      <span className="meta-icon">✓</span>
                      <span className="meta-label">Last run:</span>
                      <span className="meta-value">{formatDate(digest.last_run_at)}</span>
                    </div>
                  )}
                </div>

                <div className="digest-actions" onClick={(e) => e.stopPropagation()}>
                  <motion.button
                    className="action-btn toggle-btn"
                    onClick={() => handleToggleDigest(digest.id)}
                    whileHover={{ scale: 1.05 }}
                    whileTap={{ scale: 0.95 }}
                  >
                    <span>{digest.is_active ? '⏸' : '▶'}</span>
                  </motion.button>
                  <motion.button
                    className="action-btn run-btn"
                    onClick={() => handleTriggerRun(digest.id)}
                    whileHover={{ scale: 1.05 }}
                    whileTap={{ scale: 0.95 }}
                  >
                    <span>🔄</span>
                  </motion.button>
                  <motion.button
                    className="action-btn delete-btn"
                    onClick={() => handleDeleteDigest(digest.id)}
                    whileHover={{ scale: 1.05 }}
                    whileTap={{ scale: 0.95 }}
                  >
                    <span>🗑️</span>
                  </motion.button>
                </div>
              </motion.div>
            ))
          )}
        </motion.div>

        {/* Selected Digest Details */}
        <AnimatePresence>
          {selectedDigest && (
            <motion.div
              className="digest-details-panel"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 20 }}
            >
              <div className="details-glow" />
              
              <div className="details-header">
                <h3 className="details-title">
                  <span className="title-icon">📋</span>
                  {selectedDigest.name} - Runs
                </h3>
                <motion.button
                  className="close-details-btn"
                  onClick={() => setSelectedDigest(null)}
                  whileHover={{ scale: 1.1, rotate: 90 }}
                  whileTap={{ scale: 0.9 }}
                >
                  ✕
                </motion.button>
              </div>

              <div className="runs-list">
                {digestRuns && digestRuns.length > 0 ? (
                  digestRuns.map((run, index) => (
                    <motion.div
                      key={run.id}
                      className="run-item"
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: index * 0.1 }}
                    >
                      <div className="run-header">
                        <span className={`run-status ${run.status}`}>
                          {run.status === 'completed' ? '✓' : run.status === 'failed' ? '✕' : '⏳'}
                        </span>
                        <span className="run-date">{formatDate(run.created_at)}</span>
                      </div>
                      <div className="run-info">
                        <span className="run-count">{run.new_papers_count} new papers</span>
                        {run.error_message && (
                          <span className="run-error">{run.error_message}</span>
                        )}
                      </div>
                    </motion.div>
                  ))
                ) : (
                  <div className="no-runs">
                    <span>📭</span>
                    <p>No runs yet</p>
                  </div>
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}

export default DigestManagement