import React, { useState, useEffect, useCallback } from 'react'
import { motion } from 'framer-motion'
import { api } from '../api.js'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import { GitCompare, FileText, Loader2 } from 'lucide-react'

function SessionCompare() {
  const [sessions, setSessions] = useState([])
  const [sessionA, setSessionA] = useState(null)
  const [sessionB, setSessionB] = useState(null)
  const [selectedA, setSelectedA] = useState('')
  const [selectedB, setSelectedB] = useState('')
  const [isLoading, setIsLoading] = useState(false)

  const loadSessions = useCallback(async () => {
    try {
      const data = await api.getSessions()
      setSessions(data)
    } catch (error) {
      console.error('Error loading sessions:', error)
    }
  }, [])

  const loadSession = useCallback(async (id, setter) => {
    setIsLoading(true)
    try {
      const data = await api.getSession(id)
      setter(data)
    } catch (error) {
      console.error('Error loading session:', error)
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    loadSessions()
  }, [loadSessions])

  useEffect(() => {
    if (selectedA) {
      loadSession(selectedA, setSessionA)
    } else {
      setSessionA(null)
    }
  }, [selectedA, loadSession])

  useEffect(() => {
    if (selectedB) {
      loadSession(selectedB, setSessionB)
    } else {
      setSessionB(null)
    }
  }, [selectedB, loadSession])

  const getAnalysisMap = (session) => {
    if (!session?.analyses) return {}
    return session.analyses.reduce((acc, a) => {
      acc[a.analysis_type] = a.data_json
      return acc
    }, {})
  }

  const mergePublicationTrends = () => {
    const analysisA = getAnalysisMap(sessionA)
    const analysisB = getAnalysisMap(sessionB)
    const trendA = analysisA.publication_trend || []
    const trendB = analysisB.publication_trend || []
    const years = new Set()
    trendA.forEach(t => years.add(t.year))
    trendB.forEach(t => years.add(t.year))

    return Array.from(years).sort().map(year => ({
      year,
      [sessionA?.name || 'Session A']: trendA.find(t => t.year === year)?.count || 0,
      [sessionB?.name || 'Session B']: trendB.find(t => t.year === year)?.count || 0
    }))
  }

  const getKeywordComparison = () => {
    const analysisA = getAnalysisMap(sessionA)
    const analysisB = getAnalysisMap(sessionB)
    const keywordsA = (analysisA.keyword_frequency || []).slice(0, 8).map(k => k.word)
    const keywordsB = (analysisB.keyword_frequency || []).slice(0, 8).map(k => k.word)
    const uniqueA = keywordsA.filter(w => !keywordsB.includes(w))
    const uniqueB = keywordsB.filter(w => !keywordsA.includes(w))
    const shared = keywordsA.filter(w => keywordsB.includes(w))
    return { uniqueA, uniqueB, shared }
  }

  const getCommonPapers = () => {
    if (!sessionA?.papers || !sessionB?.papers) return 0
    const idsA = new Set(sessionA.papers.map(p => p.external_id))
    return sessionB.papers.filter(p => idsA.has(p.external_id)).length
  }

  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      return (
        <div className="card" style={{ padding: 'var(--space-3)', fontSize: 'var(--text-sm)' }}>
          <p style={{ fontWeight: 'var(--font-medium)', marginBottom: 'var(--space-1)' }}>{label}</p>
          {payload.map((entry, index) => (
            <p key={index} style={{ color: entry.color }}>
              {entry.name}: {entry.value}
            </p>
          ))}
        </div>
      )
    }
    return null
  }

  if (sessions.length < 2) {
    return (
      <div className="empty-state">
        <div className="empty-icon">
          <GitCompare size={32} strokeWidth={1} />
        </div>
        <h3 className="empty-title">Need more sessions</h3>
        <p className="empty-description">
          Create at least 2 sessions to compare them side by side
        </p>
      </div>
    )
  }

  return (
    <div>
      <div style={{ marginBottom: 'var(--space-8)' }}>
        <h1 style={{ fontSize: 'var(--text-2xl)', fontWeight: 'var(--font-bold)', marginBottom: 'var(--space-2)' }}>
          Compare Sessions
        </h1>
        <p style={{ color: 'var(--text-secondary)' }}>
          Analyze differences and similarities between research sessions
        </p>
      </div>

      {/* Selectors */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr auto 1fr', gap: 'var(--space-4)', alignItems: 'center', marginBottom: 'var(--space-8)' }}>
        <div>
          <label style={{ display: 'block', fontSize: 'var(--text-sm)', fontWeight: 'var(--font-medium)', marginBottom: 'var(--space-2)' }}>
            Session A
          </label>
          <select
            value={selectedA}
            onChange={(e) => setSelectedA(e.target.value)}
            className="form-input"
          >
            <option value="">Select session...</option>
            {sessions.map(s => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </select>
        </div>

        <div style={{ 
          width: '48px', 
          height: '48px', 
          display: 'flex', 
          alignItems: 'center', 
          justifyContent: 'center',
          fontSize: 'var(--text-sm)', 
          fontWeight: 'var(--font-bold)', 
          color: 'var(--text-tertiary)'
        }}>
          VS
        </div>

        <div>
          <label style={{ display: 'block', fontSize: 'var(--text-sm)', fontWeight: 'var(--font-medium)', marginBottom: 'var(--space-2)' }}>
            Session B
          </label>
          <select
            value={selectedB}
            onChange={(e) => setSelectedB(e.target.value)}
            className="form-input"
          >
            <option value="">Select session...</option>
            {sessions.map(s => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </select>
        </div>
      </div>

      {isLoading && (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 'var(--space-16)' }}>
          <Loader2 size={24} style={{ animation: 'spin 0.8s linear infinite', color: 'var(--text-tertiary)' }} />
        </div>
      )}

      {selectedA && selectedB && sessionA && sessionB && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
        >
          {/* Stats */}
          <div className="stats-grid" style={{ marginBottom: 'var(--space-8)' }}>
            <div className="stat-card">
              <div className="stat-label">{sessionA.name}</div>
              <div className="stat-value">{sessionA.papers?.length || 0}</div>
              <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-tertiary)' }}>papers</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">{sessionB.name}</div>
              <div className="stat-value">{sessionB.papers?.length || 0}</div>
              <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-tertiary)' }}>papers</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Overlap</div>
              <div className="stat-value">{getCommonPapers()}</div>
              <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-tertiary)' }}>common papers</div>
            </div>
          </div>

          {/* Publication Trends */}
          <div className="card" style={{ padding: 'var(--space-6)', marginBottom: 'var(--space-6)' }}>
            <h3 style={{ fontSize: 'var(--text-lg)', fontWeight: 'var(--font-semibold)', marginBottom: 'var(--space-4)' }}>
              Publication Trends
            </h3>
            {mergePublicationTrends().length > 0 ? (
              <div style={{ height: '280px' }}>
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={mergePublicationTrends()}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border-primary)" />
                    <XAxis dataKey="year" stroke="var(--text-tertiary)" fontSize={12} />
                    <YAxis stroke="var(--text-tertiary)" fontSize={12} />
                    <Tooltip content={<CustomTooltip />} />
                    <Legend />
                    <Line type="monotone" dataKey={sessionA.name} stroke="var(--accent-primary)" strokeWidth={2} dot={{ fill: 'var(--accent-primary)', r: 4 }} />
                    <Line type="monotone" dataKey={sessionB.name} stroke="var(--success-primary)" strokeWidth={2} dot={{ fill: 'var(--success-primary)', r: 4 }} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <p style={{ color: 'var(--text-tertiary)', textAlign: 'center', padding: 'var(--space-8)' }}>
                No trend data available
              </p>
            )}
          </div>

          {/* Keywords */}
          <div className="card" style={{ padding: 'var(--space-6)' }}>
            <h3 style={{ fontSize: 'var(--text-lg)', fontWeight: 'var(--font-semibold)', marginBottom: 'var(--space-4)' }}>
              Keywords
            </h3>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 'var(--space-4)' }}>
              <div>
                <div style={{ fontSize: 'var(--text-xs)', fontWeight: 'var(--font-semibold)', color: 'var(--text-tertiary)', marginBottom: 'var(--space-2)', textTransform: 'uppercase' }}>
                  {sessionA.name} (Unique)
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-1)' }}>
                  {getKeywordComparison().uniqueA.length > 0 ? (
                    getKeywordComparison().uniqueA.map((word, i) => (
                      <span key={i} className="badge badge-primary">{word}</span>
                    ))
                  ) : (
                    <span style={{ fontSize: 'var(--text-sm)', color: 'var(--text-tertiary)' }}>None</span>
                  )}
                </div>
              </div>
              <div>
                <div style={{ fontSize: 'var(--text-xs)', fontWeight: 'var(--font-semibold)', color: 'var(--text-tertiary)', marginBottom: 'var(--space-2)', textTransform: 'uppercase' }}>
                  Shared
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-1)' }}>
                  {getKeywordComparison().shared.length > 0 ? (
                    getKeywordComparison().shared.map((word, i) => (
                      <span key={i} className="badge badge-default">{word}</span>
                    ))
                  ) : (
                    <span style={{ fontSize: 'var(--text-sm)', color: 'var(--text-tertiary)' }}>None</span>
                  )}
                </div>
              </div>
              <div>
                <div style={{ fontSize: 'var(--text-xs)', fontWeight: 'var(--font-semibold)', color: 'var(--text-tertiary)', marginBottom: 'var(--space-2)', textTransform: 'uppercase' }}>
                  {sessionB.name} (Unique)
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-1)' }}>
                  {getKeywordComparison().uniqueB.length > 0 ? (
                    getKeywordComparison().uniqueB.map((word, i) => (
                      <span key={i} className="badge badge-success">{word}</span>
                    ))
                  ) : (
                    <span style={{ fontSize: 'var(--text-sm)', color: 'var(--text-tertiary)' }}>None</span>
                  )}
                </div>
              </div>
            </div>
          </div>
        </motion.div>
      )}

      {(!selectedA || !selectedB) && (
        <div className="empty-state">
          <div className="empty-icon">
            <GitCompare size={32} strokeWidth={1} />
          </div>
          <h3 className="empty-title">Select two sessions</h3>
          <p className="empty-description">
            Choose two sessions above to see their comparison
          </p>
        </div>
      )}
    </div>
  )
}

export default SessionCompare
