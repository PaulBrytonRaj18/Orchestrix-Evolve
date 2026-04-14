import React, { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { api } from '../api.js'
import { Mail, Plus, Loader2, X, Clock, Play, Trash2, Calendar } from 'lucide-react'

function DigestManagement() {
  const [digests, setDigests] = useState([])
  const [isLoading, setIsLoading] = useState(false)
  const [showCreateForm, setShowCreateForm] = useState(false)
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
    } finally {
      setIsCreating(false)
    }
  }

  const handleToggleDigest = async (digestId) => {
    try {
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
    if (!confirm('Delete this digest?')) return

    try {
      await api.deleteDigest(digestId)
      setDigests(prev => prev.filter(d => d.id !== digestId))
    } catch (error) {
      console.error('Error deleting digest:', error)
    }
  }

  const handleTriggerRun = async (digestId) => {
    try {
      await api.triggerDigestRun(digestId)
    } catch (error) {
      console.error('Error triggering digest:', error)
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
    const labels = { daily: 'Daily', weekly: 'Weekly', biweekly: 'Biweekly', monthly: 'Monthly' }
    return labels[freq] || freq
  }

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 'var(--space-8)' }}>
        <div>
          <h1 style={{ fontSize: 'var(--text-2xl)', fontWeight: 'var(--font-bold)', marginBottom: 'var(--space-2)' }}>
            Scheduled Digests
          </h1>
          <p style={{ color: 'var(--text-secondary)' }}>
            Get automatic research updates delivered to your inbox
          </p>
        </div>
        <button className="btn btn-primary" onClick={() => setShowCreateForm(true)}>
          <Plus size={16} />
          New Digest
        </button>
      </div>

      {/* Create Form Modal */}
      <AnimatePresence>
        {showCreateForm && (
          <motion.div
            className="modal-backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setShowCreateForm(false)}
          >
            <motion.div
              className="modal"
              initial={{ opacity: 0, scale: 0.95, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 20 }}
              onClick={(e) => e.stopPropagation()}
            >
              <div className="modal-header">
                <h3 className="modal-title">Create Scheduled Digest</h3>
                <button className="btn btn-ghost btn-icon" onClick={() => setShowCreateForm(false)}>
                  <X size={18} />
                </button>
              </div>
              <form onSubmit={handleCreateDigest} style={{ padding: 'var(--space-5)', display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
                <div className="form-group">
                  <label className="form-label">Name</label>
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
                  <label className="form-label">Search Query</label>
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
                  <label className="form-label">Frequency</label>
                  <select
                    className="form-input"
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
                  <label className="form-label">Email (optional)</label>
                  <input
                    type="email"
                    className="form-input"
                    placeholder="your@email.com"
                    value={formData.notify_email}
                    onChange={(e) => setFormData({ ...formData, notify_email: e.target.value })}
                  />
                </div>
                <div style={{ display: 'flex', gap: 'var(--space-3)', justifyContent: 'flex-end', marginTop: 'var(--space-2)' }}>
                  <button type="button" className="btn btn-secondary" onClick={() => setShowCreateForm(false)}>
                    Cancel
                  </button>
                  <button type="submit" className="btn btn-primary" disabled={isCreating || !formData.name.trim() || !formData.query.trim()}>
                    {isCreating ? 'Creating...' : 'Create Digest'}
                  </button>
                </div>
              </form>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Digest List */}
      {isLoading ? (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 'var(--space-16)' }}>
          <Loader2 size={24} style={{ animation: 'spin 0.8s linear infinite', color: 'var(--text-tertiary)' }} />
        </div>
      ) : digests.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">
            <Mail size={32} strokeWidth={1} />
          </div>
          <h3 className="empty-title">No scheduled digests</h3>
          <p className="empty-description">
            Create your first digest to receive automated research updates
          </p>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: 'var(--space-4)' }}>
          {digests.map((digest) => (
            <motion.div
              key={digest.id}
              className="card card-hover"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              style={{ padding: 'var(--space-5)' }}
            >
              <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 'var(--space-3)' }}>
                <div>
                  <h3 style={{ fontSize: 'var(--text-base)', fontWeight: 'var(--font-semibold)', marginBottom: 'var(--space-1)' }}>
                    {digest.name}
                  </h3>
                  <p style={{ fontSize: 'var(--text-sm)', color: 'var(--text-secondary)' }}>
                    {digest.query}
                  </p>
                </div>
                <span className={`badge ${digest.is_active ? 'badge-success' : 'badge-default'}`}>
                  {digest.is_active ? 'Active' : 'Paused'}
                </span>
              </div>

              <div style={{ display: 'flex', gap: 'var(--space-4)', fontSize: 'var(--text-sm)', color: 'var(--text-tertiary)', marginBottom: 'var(--space-4)' }}>
                <span style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-1)' }}>
                  <Calendar size={14} />
                  {getFrequencyLabel(digest.frequency)}
                </span>
                <span style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-1)' }}>
                  <Clock size={14} />
                  {formatDate(digest.next_run_at)}
                </span>
              </div>

              <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
                <button
                  className="btn btn-ghost btn-sm"
                  onClick={() => handleToggleDigest(digest.id)}
                >
                  {digest.is_active ? 'Pause' : 'Resume'}
                </button>
                <button
                  className="btn btn-ghost btn-sm"
                  onClick={() => handleTriggerRun(digest.id)}
                >
                  <Play size={14} />
                  Run now
                </button>
                <button
                  className="btn btn-ghost btn-sm"
                  onClick={() => handleDeleteDigest(digest.id)}
                  style={{ color: 'var(--error-primary)' }}
                >
                  <Trash2 size={14} />
                </button>
              </div>
            </motion.div>
          ))}
        </div>
      )}
    </div>
  )
}

export default DigestManagement
