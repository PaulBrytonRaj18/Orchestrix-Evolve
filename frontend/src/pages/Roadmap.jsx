import React, { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { api } from '../api.js'
import { useNavigate } from 'react-router-dom'

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
        } catch (error) {
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

  const toggleRoadmap = (sessionId) => {
    setExpandedRoadmap(expandedRoadmap === sessionId ? null : sessionId)
  }

  const sessionsWithRoadmaps = sessions.filter(s => roadmaps[s.id])

  return (
    <div className="roadmap-page-container">
      <motion.div
        className="roadmap-page-header"
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <h1>🗺️ Research Roadmaps</h1>
        <p>View and manage research roadmaps for all your sessions. Click "Show Roadmap" to see detailed insights.</p>
      </motion.div>

      {loading ? (
        <div className="roadmap-loading">
          <motion.div
            className="loading-spinner"
            animate={{ rotate: 360 }}
            transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
          >
            🔄
          </motion.div>
          <p>Loading roadmaps...</p>
        </div>
      ) : (
        <>
          <motion.div
            className="roadmap-stats"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
          >
            <div className="stat-card">
              <span className="stat-number">{sessions.length}</span>
              <span className="stat-label">Total Sessions</span>
            </div>
            <div className="stat-card">
              <span className="stat-number">{sessionsWithRoadmaps.length}</span>
              <span className="stat-label">Roadmaps Generated</span>
            </div>
            <div className="stat-card highlight">
              <span className="stat-number">
                {sessionsWithRoadmaps.reduce((acc, s) => {
                  const r = roadmaps[s.id]
                  return acc + (r?.foundational_papers?.length || 0)
                }, 0)}
              </span>
              <span className="stat-label">Foundational Papers</span>
            </div>
          </motion.div>

          {sessions.length === 0 ? (
            <motion.div
              className="roadmap-empty-state"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
            >
              <span className="empty-icon">🗺️</span>
              <h2>No Sessions Yet</h2>
              <p>Create a session and search for papers to generate your first roadmap.</p>
              <button onClick={() => navigate('/')} className="start-search-btn">
                🔍 Start Searching
              </button>
            </motion.div>
          ) : (
            <div className="roadmap-list">
              {sessions.map((session, index) => {
                const roadmap = roadmaps[session.id]
                const isExpanded = expandedRoadmap === session.id
                const isGenerating = generatingId === session.id
                
                return (
                  <motion.div
                    key={session.id}
                    className={`roadmap-card ${roadmap ? 'has-roadmap' : 'no-roadmap'}`}
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: index * 0.05 }}
                  >
                    {/* Card Header */}
                    <div className="roadmap-card-header">
                      <div className="header-info">
                        <h3>{session.name}</h3>
                        <span className="session-date">
                          {new Date(session.created_at).toLocaleDateString(undefined, {
                            year: 'numeric',
                            month: 'short',
                            day: 'numeric'
                          })}
                        </span>
                      </div>
                      <div className="header-actions">
                        <button
                          onClick={() => handleViewSession(session.id)}
                          className="view-session-btn"
                        >
                          📄 View Session
                        </button>
                        <button
                          onClick={() => handleGenerateRoadmap(session.id)}
                          disabled={isGenerating}
                          className="generate-btn"
                        >
                          {isGenerating ? '🔄 Generating...' : roadmap ? '🔄 Regenerate' : '✨ Generate'}
                        </button>
                      </div>
                    </div>

                    {/* Query */}
                    <div className="roadmap-card-query">
                      <span className="query-icon">🔍</span>
                      <span>{session.query}</span>
                    </div>

                    {/* Show Roadmap Button */}
                    {roadmap && (
                      <motion.button
                        className={`show-roadmap-btn ${isExpanded ? 'expanded' : ''}`}
                        onClick={() => toggleRoadmap(session.id)}
                        whileHover={{ scale: 1.01 }}
                        whileTap={{ scale: 0.99 }}
                      >
                        <span className="btn-icon">{isExpanded ? '📕' : '📗'}</span>
                        <span>{isExpanded ? 'Hide Roadmap' : 'Show Roadmap'}</span>
                        <span className="btn-arrow">{isExpanded ? '▲' : '▼'}</span>
                      </motion.button>
                    )}

                    {/* Roadmap Details - Expandable */}
                    <AnimatePresence>
                      {roadmap && isExpanded && (
                        <motion.div
                          className="roadmap-details"
                          initial={{ height: 0, opacity: 0 }}
                          animate={{ height: 'auto', opacity: 1 }}
                          exit={{ height: 0, opacity: 0 }}
                          transition={{ duration: 0.3 }}
                        >
                          {/* Foundational Papers */}
                          <div className="roadmap-section">
                            <h4>
                              <span className="section-icon">📚</span>
                              Foundational Papers
                              <span className="section-count">{roadmap.foundational_papers?.length || 0}</span>
                            </h4>
                            {roadmap.foundational_papers && roadmap.foundational_papers.length > 0 ? (
                              <div className="papers-list">
                                {roadmap.foundational_papers.map((paper, idx) => (
                                  <div key={paper.paper_id || idx} className="paper-item">
                                    <div className="paper-priority">#{paper.priority}</div>
                                    <div className="paper-content">
                                      <h5>{paper.title}</h5>
                                      <div className="paper-meta">
                                        <span className="meta-item">📅 {paper.year}</span>
                                        <span className="meta-item">📖 {paper.citation_count} citations</span>
                                      </div>
                                      <p className="paper-reason">{paper.reason}</p>
                                    </div>
                                  </div>
                                ))}
                              </div>
                            ) : (
                              <p className="no-data">No foundational papers identified yet</p>
                            )}
                          </div>

                          {/* Research Gaps */}
                          <div className="roadmap-section">
                            <h4>
                              <span className="section-icon">🔍</span>
                              Research Gaps
                              <span className="section-count">{roadmap.gap_areas?.length || 0}</span>
                            </h4>
                            {roadmap.gap_areas && roadmap.gap_areas.length > 0 ? (
                              <div className="gaps-list">
                                {roadmap.gap_areas.map((gap, idx) => (
                                  <div key={idx} className={`gap-item severity-${gap.severity}`}>
                                    <div className="gap-header">
                                      <span className={`severity-badge ${gap.severity}`}>
                                        {gap.severity.toUpperCase()}
                                      </span>
                                      <h5>{gap.question}</h5>
                                    </div>
                                    <p className="gap-evidence">{gap.evidence}</p>
                                    {gap.related_papers && gap.related_papers.length > 0 && (
                                      <div className="related-papers">
                                        <span>📄 Related to {gap.related_papers.length} paper(s)</span>
                                      </div>
                                    )}
                                  </div>
                                ))}
                              </div>
                            ) : (
                              <p className="no-data">No research gaps identified yet</p>
                            )}
                          </div>

                          {/* Future Steps / Next Queries */}
                          <div className="roadmap-section">
                            <h4>
                              <span className="section-icon">🎯</span>
                              Future Steps
                              <span className="section-count">{roadmap.next_query_suggestions?.length || 0}</span>
                            </h4>
                            {roadmap.next_query_suggestions && roadmap.next_query_suggestions.length > 0 ? (
                              <div className="queries-list">
                                {roadmap.next_query_suggestions.map((q, idx) => (
                                  <div key={idx} className="query-item">
                                    <div className="query-main">
                                      <span className="query-number">{idx + 1}</span>
                                      <span className="query-text">{q.query}</span>
                                    </div>
                                    <div className="query-details">
                                      <span className="query-rationale">💡 {q.rationale}</span>
                                      <span className="query-insight">✨ Expected: {q.expected_insight}</span>
                                    </div>
                                  </div>
                                ))}
                              </div>
                            ) : (
                              <p className="no-data">No next steps suggested yet</p>
                            )}
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>

                    {/* No Roadmap Message */}
                    {!roadmap && (
                      <div className="no-roadmap-message">
                        <span>📝</span>
                        <p>Generate a roadmap to see detailed insights about foundational papers, research gaps, and future directions.</p>
                      </div>
                    )}
                  </motion.div>
                )
              })}
            </div>
          )}
        </>
      )}
    </div>
  )
}

export default Roadmap
