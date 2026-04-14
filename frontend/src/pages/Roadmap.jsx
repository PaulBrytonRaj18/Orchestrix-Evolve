import React, { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { api } from '../api.js'
import { useNavigate } from 'react-router-dom'
import { Map, FileText, Plus, ChevronDown, ChevronUp, Loader2, RefreshCw } from 'lucide-react'

function Roadmap() {
  const navigate = useNavigate()
  const [sessions, setSessions] = useState([])
  const [loading, setLoading] = useState(true)
  const [roadmaps, setRoadmaps] = useState({})
  const [expandedRoadmap, setExpandedRoadmap] = useState(null)
  const [generatingId, setGeneratingId] = useState(null)

  useEffect(() => {
    fetchSessionsAndRoadmaps()
  }, [])

  const fetchSessionsAndRoadmaps = async () => {
    setLoading(true)
    try {
      const sessionsData = await api.getSessions()
      setSessions(sessionsData)
      
      const roadmapPromises = sessionsData.map(async (session) => {
        try {
          const roadmap = await api.getRoadmap(session.id)
          return { [session.id]: roadmap }
        } catch {
          return { [session.id]: null }
        }
      })
      
      const roadmapResults = await Promise.all(roadmapPromises)
      const roadmapMap = Object.assign({}, ...roadmapResults)
      setRoadmaps(roadmapMap)
    } catch (error) {
      console.error('Error fetching sessions:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleGenerateRoadmap = async (sessionId) => {
    setGeneratingId(sessionId)
    try {
      await api.generateRoadmap(sessionId)
      await fetchSessionsAndRoadmaps()
      setExpandedRoadmap(sessionId)
    } catch (error) {
      console.error('Error generating roadmap:', error)
    } finally {
      setGeneratingId(null)
    }
  }

  const handleViewSession = (sessionId) => {
    navigate(`/dashboard/${sessionId}`)
  }

  const sessionsWithRoadmaps = sessions.filter(s => roadmaps[s.id])

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '300px' }}>
        <Loader2 size={24} style={{ animation: 'spin 0.8s linear infinite', color: 'var(--text-tertiary)' }} />
      </div>
    )
  }

  return (
    <div>
      <div style={{ marginBottom: 'var(--space-8)' }}>
        <h1 style={{ fontSize: 'var(--text-2xl)', fontWeight: 'var(--font-bold)', marginBottom: 'var(--space-2)' }}>
          Research Roadmaps
        </h1>
        <p style={{ color: 'var(--text-secondary)' }}>
          AI-generated research directions and foundational papers
        </p>
      </div>

      {sessions.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">
            <Map size={32} strokeWidth={1} />
          </div>
          <h3 className="empty-title">No sessions yet</h3>
          <p className="empty-description">
            Start a search to create your first research roadmap
          </p>
          <button onClick={() => navigate('/')} className="btn btn-primary" style={{ marginTop: 'var(--space-4)' }}>
            <Plus size={16} />
            Start Searching
          </button>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
          {sessions.map((session) => {
            const roadmap = roadmaps[session.id]
            const isExpanded = expandedRoadmap === session.id
            const isGenerating = generatingId === session.id
            
            return (
              <div key={session.id} className="card">
                <div style={{ padding: 'var(--space-5)' }}>
                  <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 'var(--space-4)' }}>
                    <div style={{ flex: 1 }}>
                      <h3 style={{ fontSize: 'var(--text-base)', fontWeight: 'var(--font-semibold)', marginBottom: 'var(--space-1)' }}>
                        {session.name}
                      </h3>
                      <p style={{ fontSize: 'var(--text-sm)', color: 'var(--text-secondary)' }}>
                        {session.query}
                      </p>
                    </div>
                    <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
                      <button
                        className="btn btn-ghost btn-sm"
                        onClick={() => handleViewSession(session.id)}
                      >
                        <FileText size={14} />
                        View
                      </button>
                      <button
                        className="btn btn-secondary btn-sm"
                        onClick={() => handleGenerateRoadmap(session.id)}
                        disabled={isGenerating}
                      >
                        {isGenerating ? (
                          <Loader2 size={14} style={{ animation: 'spin 0.8s linear infinite' }} />
                        ) : (
                          <RefreshCw size={14} />
                        )}
                        {roadmap ? 'Regenerate' : 'Generate'}
                      </button>
                    </div>
                  </div>

                  {roadmap && (
                    <button
                      onClick={() => setExpandedRoadmap(isExpanded ? null : session.id)}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 'var(--space-2)',
                        marginTop: 'var(--space-4)',
                        padding: 'var(--space-2) var(--space-3)',
                        fontSize: 'var(--text-sm)',
                        color: 'var(--accent-primary)',
                        background: 'var(--accent-subtle)',
                        borderRadius: 'var(--radius-md)',
                        width: '100%',
                        justifyContent: 'center'
                      }}
                    >
                      {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                      {isExpanded ? 'Hide' : 'Show'} Roadmap
                    </button>
                  )}
                </div>

                <AnimatePresence>
                  {roadmap && isExpanded && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: 'auto', opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      style={{ borderTop: '1px solid var(--card-border)' }}
                    >
                      <div style={{ padding: 'var(--space-5)' }}>
                        {/* Foundational Papers */}
                        {roadmap.foundational_papers?.length > 0 && (
                          <div style={{ marginBottom: 'var(--space-6)' }}>
                            <h4 style={{ fontSize: 'var(--text-sm)', fontWeight: 'var(--font-semibold)', marginBottom: 'var(--space-3)', color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                              Foundational Papers
                            </h4>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
                              {roadmap.foundational_papers.slice(0, 5).map((paper, idx) => (
                                <div key={paper.paper_id || idx} style={{ display: 'flex', gap: 'var(--space-3)', padding: 'var(--space-3)', background: 'var(--bg-secondary)', borderRadius: 'var(--radius-md)' }}>
                                  <span style={{ fontSize: 'var(--text-xs)', fontWeight: 'var(--font-semibold)', color: 'var(--accent-primary)', minWidth: '24px' }}>
                                    #{paper.priority}
                                  </span>
                                  <div style={{ flex: 1 }}>
                                    <p style={{ fontSize: 'var(--text-sm)', fontWeight: 'var(--font-medium)', marginBottom: 'var(--space-1)' }}>
                                      {paper.title}
                                    </p>
                                    <p style={{ fontSize: 'var(--text-xs)', color: 'var(--text-tertiary)' }}>
                                      {paper.year} • {paper.citation_count} citations
                                    </p>
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Gap Areas */}
                        {roadmap.gap_areas?.length > 0 && (
                          <div style={{ marginBottom: 'var(--space-6)' }}>
                            <h4 style={{ fontSize: 'var(--text-sm)', fontWeight: 'var(--font-semibold)', marginBottom: 'var(--space-3)', color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                              Research Gaps
                            </h4>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
                              {roadmap.gap_areas.map((gap, idx) => (
                                <div key={idx} style={{ padding: 'var(--space-3)', background: 'var(--bg-secondary)', borderRadius: 'var(--radius-md)' }}>
                                  <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', marginBottom: 'var(--space-2)' }}>
                                    <span className={`badge badge-${gap.severity === 'high' ? 'error' : gap.severity === 'medium' ? 'warning' : 'default'}`}>
                                      {gap.severity}
                                    </span>
                                  </div>
                                  <p style={{ fontSize: 'var(--text-sm)', fontWeight: 'var(--font-medium)', marginBottom: 'var(--space-1)' }}>
                                    {gap.question}
                                  </p>
                                  <p style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>
                                    {gap.evidence}
                                  </p>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Next Steps */}
                        {roadmap.next_query_suggestions?.length > 0 && (
                          <div>
                            <h4 style={{ fontSize: 'var(--text-sm)', fontWeight: 'var(--font-semibold)', marginBottom: 'var(--space-3)', color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                              Suggested Research
                            </h4>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
                              {roadmap.next_query_suggestions.slice(0, 5).map((q, idx) => (
                                <div key={idx} style={{ padding: 'var(--space-3)', background: 'var(--bg-secondary)', borderRadius: 'var(--radius-md)' }}>
                                  <p style={{ fontSize: 'var(--text-sm)', fontWeight: 'var(--font-medium)', marginBottom: 'var(--space-1)' }}>
                                    {q.query}
                                  </p>
                                  <p style={{ fontSize: 'var(--text-xs)', color: 'var(--text-tertiary)' }}>
                                    {q.rationale}
                                  </p>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

export default Roadmap
