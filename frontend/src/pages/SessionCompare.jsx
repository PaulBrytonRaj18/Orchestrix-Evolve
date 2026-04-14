import React, { useState, useEffect, useCallback, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import '../sessioncompare.css'
import { api } from '../api.js'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend
} from 'recharts'

const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.1,
      delayChildren: 0.2
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
    scale: [1, 1.05, 1],
    opacity: [0.7, 1, 0.7],
    transition: {
      duration: 2,
      repeat: Infinity,
      ease: "easeInOut"
    }
  }
}

function SessionCompare() {
  const [sessions, setSessions] = useState([])
  const [sessionA, setSessionA] = useState(null)
  const [sessionB, setSessionB] = useState(null)
  const [selectedA, setSelectedA] = useState('')
  const [selectedB, setSelectedB] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [mousePosition, setMousePosition] = useState({ x: 0, y: 0 })
  const containerRef = useRef(null)

  useEffect(() => {
    const handleMouseMove = (e) => {
      if (containerRef.current) {
        setMousePosition({ x: e.clientX, y: e.clientY })
      }
    }
    window.addEventListener('mousemove', handleMouseMove)
    return () => window.removeEventListener('mousemove', handleMouseMove)
  }, [])

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
    return sessionB.papers.filter(p => idsA.has(p.external_id)).length
  }

  const renderPaperList = (session, variant) => {
    if (!session?.papers?.length) {
      return (
        <div className="compare-empty-papers">
          <span>📭</span>
          <p>No papers in this session</p>
        </div>
      )
    }

    return (
      <motion.div
        variants={containerVariants}
        initial="hidden"
        animate="visible"
        className="compare-papers-list"
      >
        {session.papers.map((paper, index) => (
          <motion.div
            key={paper.id}
            variants={itemVariants}
            className={`compare-paper-item ${variant}`}
            whileHover={{ scale: 1.02, x: 4 }}
          >
            <div className="compare-paper-title">
              {paper.title.length > 60 ? paper.title.slice(0, 60) + '...' : paper.title}
            </div>
            <div className="compare-paper-meta">
              {paper.authors?.slice(0, 2).join(', ')}
              {paper.authors?.length > 2 && ' et al.'}
              {' • '}{paper.year}
            </div>
          </motion.div>
        ))}
      </motion.div>
    )
  }

  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      return (
        <div className="compare-chart-tooltip">
          <p className="tooltip-label">{label}</p>
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

  const renderComparisonPanel = () => {
    if (!sessionA || !sessionB) return null

    const mergedTrends = mergePublicationTrends()
    const keywordComparison = getKeywordComparison()
    const commonCount = getCommonPapers()

    return (
      <motion.div
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3, duration: 0.5 }}
        className="compare-analysis-panel"
      >
        <motion.div className="compare-panel-glow" animate={{ opacity: [0.3, 0.6, 0.3] }} transition={{ duration: 4, repeat: Infinity }} />
        
        <h3 className="compare-panel-title">
          <span className="title-icon">📊</span>
          Comparison Analysis
        </h3>

        {/* Publication Trends Chart */}
        <motion.div
          className="compare-chart-section"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.4 }}
        >
          <h4 className="compare-section-title">
            <span>📈</span> Publication Trends
          </h4>
          {mergedTrends.length > 0 ? (
            <div className="compare-chart-container">
              <ResponsiveContainer width="100%" height={280}>
                <LineChart data={mergedTrends}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(220, 38, 38, 0.1)" />
                  <XAxis dataKey="year" stroke="#71717a" tick={{ fill: '#a1a1aa' }} />
                  <YAxis stroke="#71717a" tick={{ fill: '#a1a1aa' }} />
                  <Tooltip content={<CustomTooltip />} />
                  <Legend wrapperStyle={{ color: '#a1a1aa' }} />
                  <Line
                    type="monotone"
                    dataKey={sessionA.name}
                    stroke="#dc2626"
                    strokeWidth={3}
                    dot={{ fill: '#dc2626', r: 5, strokeWidth: 2, stroke: '#0a0a0a' }}
                    activeDot={{ r: 8, fill: '#dc2626', stroke: '#fff', strokeWidth: 2 }}
                  />
                  <Line
                    type="monotone"
                    dataKey={sessionB.name}
                    stroke="#f97316"
                    strokeWidth={3}
                    dot={{ fill: '#f97316', r: 5, strokeWidth: 2, stroke: '#0a0a0a' }}
                    activeDot={{ r: 8, fill: '#f97316', stroke: '#fff', strokeWidth: 2 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="compare-no-data">No trend data available</div>
          )}
        </motion.div>

        {/* Keywords Comparison */}
        <motion.div
          className="compare-keywords-section"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.5 }}
        >
          <h4 className="compare-section-title">
            <span>🏷️</span> Keyword Analysis
          </h4>
          <div className="compare-keywords-grid">
            <div className="keywords-column session-a">
              <div className="keywords-header">
                <span className="session-indicator a"></span>
                {sessionA.name} (Unique)
              </div>
              <div className="keywords-tags">
                {keywordComparison.uniqueA.length > 0 ? (
                  keywordComparison.uniqueA.map((word, i) => (
                    <motion.span
                      key={i}
                      className="keyword-tag a"
                      initial={{ scale: 0 }}
                      animate={{ scale: 1 }}
                      transition={{ delay: 0.1 * i }}
                      whileHover={{ scale: 1.1 }}
                    >
                      {word}
                    </motion.span>
                  ))
                ) : (
                  <span className="no-keywords">No unique keywords</span>
                )}
              </div>
            </div>

            <div className="keywords-column shared">
              <div className="keywords-header">
                <span className="session-indicator shared"></span>
                Shared Keywords
              </div>
              <div className="keywords-tags">
                {keywordComparison.shared.length > 0 ? (
                  keywordComparison.shared.map((word, i) => (
                    <motion.span
                      key={i}
                      className="keyword-tag shared"
                      initial={{ scale: 0 }}
                      animate={{ scale: 1 }}
                      transition={{ delay: 0.1 * i }}
                      whileHover={{ scale: 1.1 }}
                    >
                      {word}
                    </motion.span>
                  ))
                ) : (
                  <span className="no-keywords">No shared keywords</span>
                )}
              </div>
            </div>

            <div className="keywords-column session-b">
              <div className="keywords-header">
                <span className="session-indicator b"></span>
                {sessionB.name} (Unique)
              </div>
              <div className="keywords-tags">
                {keywordComparison.uniqueB.length > 0 ? (
                  keywordComparison.uniqueB.map((word, i) => (
                    <motion.span
                      key={i}
                      className="keyword-tag b"
                      initial={{ scale: 0 }}
                      animate={{ scale: 1 }}
                      transition={{ delay: 0.1 * i }}
                      whileHover={{ scale: 1.1 }}
                    >
                      {word}
                    </motion.span>
                  ))
                ) : (
                  <span className="no-keywords">No unique keywords</span>
                )}
              </div>
            </div>
          </div>
        </motion.div>

        {/* Overlap Stats */}
        <motion.div
          className="compare-overlap-section"
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.6 }}
        >
          <h4 className="compare-section-title">
            <span>🔗</span> Paper Overlap
          </h4>
          <div className="overlap-stats-container">
            <motion.div
              className="overlap-stat-card"
              whileHover={{ scale: 1.05, boxShadow: "0 0 40px rgba(220, 38, 38, 0.4)" }}
            >
              <motion.div
                className="overlap-number"
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ type: "spring", stiffness: 200, delay: 0.7 }}
              >
                {commonCount}
              </motion.div>
              <div className="overlap-label">Common Papers</div>
              <div className="overlap-sublabel">appear in both sessions</div>
            </motion.div>

            <div className="overlap-visual">
              <div className="venn-diagram">
                <motion.div
                  className="venn-circle a"
                  animate={{ scale: [1, 1.05, 1] }}
                  transition={{ duration: 3, repeat: Infinity }}
                >
                  <span>{sessionA?.papers?.length || 0}</span>
                </motion.div>
                <motion.div
                  className="venn-overlap"
                  animate={{ opacity: [0.5, 1, 0.5] }}
                  transition={{ duration: 2, repeat: Infinity }}
                >
                  {commonCount}
                </motion.div>
                <motion.div
                  className="venn-circle b"
                  animate={{ scale: [1, 1.05, 1] }}
                  transition={{ duration: 3, repeat: Infinity, delay: 0.5 }}
                >
                  <span>{sessionB?.papers?.length || 0}</span>
                </motion.div>
              </div>
            </div>
          </div>
        </motion.div>
      </motion.div>
    )
  }

  return (
    <div ref={containerRef} className="compare-container">
      {/* Animated background spotlight */}
      <motion.div
        className="compare-spotlight"
        animate={{ left: mousePosition.x, top: mousePosition.y }}
        transition={{ type: "spring", damping: 30, stiffness: 200 }}
      />

      {/* Floating particles */}
      <div className="compare-particles">
        {[...Array(25)].map((_, i) => (
          <motion.div
            key={i}
            className="compare-particle"
            animate={{
              y: [0, -40, 0],
              x: [0, Math.random() * 15 - 7.5, 0],
              opacity: [0.1, 0.5, 0.1],
              scale: [0.8, 1.1, 0.8]
            }}
            transition={{
              duration: 4 + Math.random() * 2,
              repeat: Infinity,
              delay: Math.random() * 3,
              ease: "easeInOut"
            }}
            style={{
              left: `${Math.random() * 100}%`,
              top: `${Math.random() * 100}%`
            }}
          />
        ))}
      </div>

      {/* Header */}
      <motion.header
        className="compare-header"
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
      >
        <motion.div
          className="compare-header-glow"
          animate={{ scale: [1, 1.2, 1], opacity: [0.4, 0.7, 0.4] }}
          transition={{ duration: 3, repeat: Infinity }}
        />
        <div className="compare-header-content">
          <motion.div
            className="compare-header-icon"
            animate={{ rotateY: [0, 360] }}
            transition={{ duration: 8, repeat: Infinity, ease: "linear" }}
          >
            ⚖️
          </motion.div>
          <div>
            <h1 className="compare-title">Session Compare</h1>
            <p className="compare-subtitle">Analyze and compare research sessions side by side</p>
          </div>
        </div>
      </motion.header>

      {/* Session Selectors */}
      <motion.div
        className="compare-selectors"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
      >
        <motion.div
          className="selector-card session-a"
          whileHover={{ scale: 1.02, boxShadow: "0 0 40px rgba(220, 38, 38, 0.3)" }}
        >
          <div className="selector-header">
            <span className="selector-icon">🔴</span>
            <label className="selector-label">Session A</label>
          </div>
          <select
            value={selectedA}
            onChange={(e) => setSelectedA(e.target.value)}
            className="compare-select"
          >
            <option value="">Select a session...</option>
            {sessions.map(s => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </select>
        </motion.div>

        <motion.div
          className="selector-vs"
          animate={{ scale: [1, 1.1, 1], rotate: [0, 5, -5, 0] }}
          transition={{ duration: 2, repeat: Infinity }}
        >
          VS
        </motion.div>

        <motion.div
          className="selector-card session-b"
          whileHover={{ scale: 1.02, boxShadow: "0 0 40px rgba(249, 115, 22, 0.3)" }}
        >
          <div className="selector-header">
            <span className="selector-icon">🟠</span>
            <label className="selector-label">Session B</label>
          </div>
          <select
            value={selectedB}
            onChange={(e) => setSelectedB(e.target.value)}
            className="compare-select"
          >
            <option value="">Select a session...</option>
            {sessions.map(s => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </select>
        </motion.div>
      </motion.div>

      {/* Loading State */}
      <AnimatePresence>
        {isLoading && (
          <motion.div
            className="compare-loading"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
            <motion.div
              className="compare-spinner"
              animate={{ rotate: 360 }}
              transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
            />
            <p>Loading session data...</p>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Session Cards */}
      <AnimatePresence>
        {selectedA && selectedB && sessionA && sessionB && (
          <motion.div
            className="compare-sessions-grid"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            transition={{ delay: 0.2 }}
          >
            <motion.div
              className="compare-session-card session-a"
              initial={{ x: -50, opacity: 0 }}
              animate={{ x: 0, opacity: 1 }}
              transition={{ delay: 0.3 }}
            >
              <motion.div className="session-card-glow a" animate={{ opacity: [0.3, 0.6, 0.3] }} transition={{ duration: 3, repeat: Infinity }} />
              <div className="session-card-header">
                <h3 className="session-card-title">{sessionA.name}</h3>
                <motion.div
                  className="session-card-badge"
                  whileHover={{ scale: 1.1 }}
                >
                  {sessionA.papers?.length || 0} papers
                </motion.div>
              </div>
              <div className="session-card-query">
                <span className="query-icon">🔍</span>
                {sessionA.query}
              </div>
              <div className="session-papers-scroll">
                {renderPaperList(sessionA, 'a')}
              </div>
            </motion.div>

            <motion.div
              className="compare-session-card session-b"
              initial={{ x: 50, opacity: 0 }}
              animate={{ x: 0, opacity: 1 }}
              transition={{ delay: 0.4 }}
            >
              <motion.div className="session-card-glow b" animate={{ opacity: [0.3, 0.6, 0.3] }} transition={{ duration: 3, repeat: Infinity, delay: 0.5 }} />
              <div className="session-card-header">
                <h3 className="session-card-title">{sessionB.name}</h3>
                <motion.div
                  className="session-card-badge"
                  whileHover={{ scale: 1.1 }}
                >
                  {sessionB.papers?.length || 0} papers
                </motion.div>
              </div>
              <div className="session-card-query">
                <span className="query-icon">🔍</span>
                {sessionB.query}
              </div>
              <div className="session-papers-scroll">
                {renderPaperList(sessionB, 'b')}
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Comparison Panel */}
      {renderComparisonPanel()}

      {/* Empty State */}
      <AnimatePresence>
        {(!selectedA || !selectedB) && (
          <motion.div
            className="compare-empty-state"
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.9 }}
          >
            <motion.div
              className="compare-empty-glow"
              animate={{ scale: [1, 1.3, 1], opacity: [0.3, 0.6, 0.3] }}
              transition={{ duration: 3, repeat: Infinity }}
            />
            <motion.div
              className="compare-empty-icon"
              animate={{ y: [0, -15, 0], rotateZ: [0, 10, -10, 0] }}
              transition={{ duration: 3, repeat: Infinity }}
            >
              ⚖️
            </motion.div>
            <h2 className="compare-empty-title">Ready to Compare</h2>
            <p className="compare-empty-subtitle">
              Select two sessions above to analyze their differences and similarities
            </p>
            <div className="compare-empty-features">
              <motion.div className="feature-item" whileHover={{ scale: 1.05, x: 5 }}>
                <span>📈</span> Publication Trends
              </motion.div>
              <motion.div className="feature-item" whileHover={{ scale: 1.05, x: 5 }}>
                <span>🏷️</span> Keyword Analysis
              </motion.div>
              <motion.div className="feature-item" whileHover={{ scale: 1.05, x: 5 }}>
                <span>🔗</span> Paper Overlap
              </motion.div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

export default SessionCompare
