import React, { useState, useEffect, useCallback } from 'react'
import { api } from '../api.js'
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend
} from 'recharts'

function SessionCompare() {
  const [sessions, setSessions] = useState([])
  const [sessionA, setSessionA] = useState(null)
  const [sessionB, setSessionB] = useState(null)
  const [selectedA, setSelectedA] = useState('')
  const [selectedB, setSelectedB] = useState('')

  const loadSessions = useCallback(async () => {
    try {
      const data = await api.getSessions()
      setSessions(data)
    } catch (error) {
      console.error('Error loading sessions:', error)
    }
  }, [])

  const loadSession = useCallback(async (id, setter) => {
    try {
      const data = await api.getSession(id)
      setter(data)
    } catch (error) {
      console.error('Error loading session:', error)
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

    const keywordsA = (analysisA.keyword_frequency || []).slice(0, 10).map(k => k.word)
    const keywordsB = (analysisB.keyword_frequency || []).slice(0, 10).map(k => k.word)

    const uniqueA = keywordsA.filter(w => !keywordsB.includes(w))
    const uniqueB = keywordsB.filter(w => !keywordsA.includes(w))
    const shared = keywordsA.filter(w => keywordsB.includes(w))

    return { uniqueA, uniqueB, shared }
  }

  const getCommonPapers = () => {
    if (!sessionA?.papers || !sessionB?.papers) return 0

    const idsA = new Set(sessionA.papers.map(p => p.external_id))
    const common = sessionB.papers.filter(p => idsA.has(p.external_id))
    return common.length
  }

  const renderPaperList = (session) => {
    if (!session?.papers?.length) {
      return (
        <div style={{ color: '#64748b', fontStyle: 'italic', padding: '1rem' }}>
          No papers
        </div>
      )
    }

    return session.papers.map(paper => (
      <div
        key={paper.id}
        style={{
          padding: '0.75rem',
          background: '#0f172a',
          borderRadius: '8px',
          marginBottom: '0.5rem'
        }}
      >
        <div style={{ color: '#f1f5f9', fontSize: '0.875rem', fontWeight: '500', marginBottom: '0.25rem' }}>
          {paper.title.length > 60 ? paper.title.slice(0, 60) + '...' : paper.title}
        </div>
        <div style={{ color: '#64748b', fontSize: '0.75rem' }}>
          {paper.authors?.slice(0, 2).join(', ')}
          {paper.authors?.length > 2 && ' et al.'}
          {' • '}{paper.year}
        </div>
      </div>
    ))
  }

  const renderComparisonPanel = () => {
    if (!sessionA || !sessionB) return null

    const mergedTrends = mergePublicationTrends()
    const keywordComparison = getKeywordComparison()
    const commonCount = getCommonPapers()

    return (
      <div style={{
        background: '#1e293b',
        borderRadius: '12px',
        padding: '1.5rem',
        marginTop: '2rem',
        border: '1px solid #334155'
      }}>
        <h3 style={{ color: '#f1f5f9', marginBottom: '1.5rem' }}>Session Comparison</h3>

        <div style={{ marginBottom: '2rem' }}>
          <h4 style={{ color: '#60a5fa', marginBottom: '1rem' }}>Publication Trends</h4>
          {mergedTrends.length > 0 ? (
            <ResponsiveContainer width="100%" height={250}>
              <LineChart data={mergedTrends}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis dataKey="year" stroke="#94a3b8" />
                <YAxis stroke="#94a3b8" />
                <Tooltip
                  contentStyle={{ background: '#0f172a', border: '1px solid #334155', borderRadius: '8px' }}
                />
                <Legend />
                <Line
                  type="monotone"
                  dataKey={sessionA.name}
                  stroke="#60a5fa"
                  strokeWidth={2}
                  dot={{ fill: '#60a5fa', r: 4 }}
                />
                <Line
                  type="monotone"
                  dataKey={sessionB.name}
                  stroke="#a78bfa"
                  strokeWidth={2}
                  dot={{ fill: '#a78bfa', r: 4 }}
                />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div style={{ color: '#64748b', fontStyle: 'italic' }}>No trend data available</div>
          )}
        </div>

        <div style={{ marginBottom: '2rem' }}>
          <h4 style={{ color: '#60a5fa', marginBottom: '1rem' }}>Top Keywords</h4>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
            <div>
              <div style={{ color: '#60a5fa', fontSize: '0.875rem', marginBottom: '0.5rem' }}>
                {sessionA.name} (unique)
              </div>
              {keywordComparison.uniqueA.length > 0 ? (
                keywordComparison.uniqueA.map((word, i) => (
                  <span
                    key={i}
                    style={{
                      display: 'inline-block',
                      background: '#60a5fa20',
                      color: '#60a5fa',
                      padding: '0.25rem 0.5rem',
                      borderRadius: '4px',
                      margin: '0.25rem',
                      fontSize: '0.75rem'
                    }}
                  >
                    {word}
                  </span>
                ))
              ) : (
                <div style={{ color: '#64748b', fontSize: '0.875rem' }}>No unique keywords</div>
              )}
            </div>
            <div>
              <div style={{ color: '#a78bfa', fontSize: '0.875rem', marginBottom: '0.5rem' }}>
                {sessionB.name} (unique)
              </div>
              {keywordComparison.uniqueB.length > 0 ? (
                keywordComparison.uniqueB.map((word, i) => (
                  <span
                    key={i}
                    style={{
                      display: 'inline-block',
                      background: '#a78bfa20',
                      color: '#a78bfa',
                      padding: '0.25rem 0.5rem',
                      borderRadius: '4px',
                      margin: '0.25rem',
                      fontSize: '0.75rem'
                    }}
                  >
                    {word}
                  </span>
                ))
              ) : (
                <div style={{ color: '#64748b', fontSize: '0.875rem' }}>No unique keywords</div>
              )}
            </div>
          </div>
        </div>

        <div>
          <h4 style={{ color: '#60a5fa', marginBottom: '1rem' }}>Overlap</h4>
          <div style={{
            background: '#0f172a',
            padding: '1rem',
            borderRadius: '8px',
            textAlign: 'center'
          }}>
            <div style={{ fontSize: '2rem', fontWeight: 'bold', color: '#22c55e' }}>
              {commonCount}
            </div>
            <div style={{ color: '#94a3b8', fontSize: '0.875rem' }}>
              papers appear in both sessions
            </div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div style={{ maxWidth: '1400px', margin: '0 auto' }}>
      <h1 style={{ color: '#f1f5f9', marginBottom: '2rem' }}>Session Compare</h1>

      <div style={{
        display: 'grid',
        gridTemplateColumns: '1fr 1fr',
        gap: '1.5rem',
        marginBottom: '1rem'
      }}>
        <div>
          <label style={{ color: '#94a3b8', display: 'block', marginBottom: '0.5rem' }}>
            Session A
          </label>
          <select
            value={selectedA}
            onChange={(e) => setSelectedA(e.target.value)}
            style={{
              width: '100%',
              padding: '0.75rem',
              background: '#1e293b',
              border: '1px solid #334155',
              borderRadius: '8px',
              color: '#e2e8f0',
              fontSize: '1rem'
            }}
          >
            <option value="">Select a session...</option>
            {sessions.map(s => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </select>
        </div>
        <div>
          <label style={{ color: '#94a3b8', display: 'block', marginBottom: '0.5rem' }}>
            Session B
          </label>
          <select
            value={selectedB}
            onChange={(e) => setSelectedB(e.target.value)}
            style={{
              width: '100%',
              padding: '0.75rem',
              background: '#1e293b',
              border: '1px solid #334155',
              borderRadius: '8px',
              color: '#e2e8f0',
              fontSize: '1rem'
            }}
          >
            <option value="">Select a session...</option>
            {sessions.map(s => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </select>
        </div>
      </div>

      {selectedA && selectedB && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem' }}>
          <div style={{
            background: '#1e293b',
            padding: '1.5rem',
            borderRadius: '12px',
            border: '1px solid #60a5fa'
          }}>
            <h3 style={{ color: '#60a5fa', marginBottom: '1rem' }}>{sessionA?.name || 'Session A'}</h3>
            <div style={{ color: '#94a3b8', fontSize: '0.875rem', marginBottom: '1rem' }}>
              {sessionA?.papers?.length || 0} papers
            </div>
            <div style={{ maxHeight: '400px', overflow: 'auto' }}>
              {renderPaperList(sessionA)}
            </div>
          </div>

          <div style={{
            background: '#1e293b',
            padding: '1.5rem',
            borderRadius: '12px',
            border: '1px solid #a78bfa'
          }}>
            <h3 style={{ color: '#a78bfa', marginBottom: '1rem' }}>{sessionB?.name || 'Session B'}</h3>
            <div style={{ color: '#94a3b8', fontSize: '0.875rem', marginBottom: '1rem' }}>
              {sessionB?.papers?.length || 0} papers
            </div>
            <div style={{ maxHeight: '400px', overflow: 'auto' }}>
              {renderPaperList(sessionB)}
            </div>
          </div>
        </div>
      )}

      {renderComparisonPanel()}

      {(!selectedA || !selectedB) && (
        <div style={{
          background: '#1e293b',
          padding: '3rem',
          borderRadius: '12px',
          textAlign: 'center',
          marginTop: '2rem',
          border: '1px solid #334155'
        }}>
          <div style={{ color: '#64748b', fontSize: '2rem', marginBottom: '1rem' }}>⚖️</div>
          <p style={{ color: '#94a3b8' }}>
            Select two sessions above to compare them
          </p>
        </div>
      )}
    </div>
  )
}

export default SessionCompare
