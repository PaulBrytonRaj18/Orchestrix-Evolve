import React, { useState, useEffect, useCallback, useRef } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { api } from '../api.js'
import SessionSidebar from '../components/SessionSidebar.jsx'
import PaperCard from '../components/PaperCard.jsx'
import AnalysisCharts from '../components/AnalysisCharts.jsx'
import CitationPanel from '../components/CitationPanel.jsx'
import SummaryPanel from '../components/SummaryPanel.jsx'
import ConflictsPanel from '../components/ConflictsPanel.jsx'


// Animation variants
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

const tabContentVariants = {
  hidden: { opacity: 0, x: -20 },
  visible: { 
    opacity: 1, 
    x: 0,
    transition: { duration: 0.3, ease: "easeOut" }
  },
  exit: { 
    opacity: 0, 
    x: 20,
    transition: { duration: 0.2 }
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

const glowVariants = {
  glow: {
    boxShadow: [
      "0 0 20px rgba(220, 38, 38, 0.2)",
      "0 0 40px rgba(220, 38, 38, 0.4)",
      "0 0 20px rgba(220, 38, 38, 0.2)"
    ],
    transition: {
      duration: 2,
      repeat: Infinity,
      ease: "easeInOut"
    }
  }
}

function Dashboard() {
  const navigate = useNavigate()
  const { sessionId: urlSessionId } = useParams()
  const [sessions, setSessions] = useState([])
  const [currentSessionId, setCurrentSessionId] = useState(urlSessionId || null)
  const [currentSession, setCurrentSession] = useState(null)
  const [activeTab, setActiveTab] = useState('papers')
  const [debouncedNoteChanges, setDebouncedNoteChanges] = useState({})
  const [isLoading, setIsLoading] = useState(false)
  const [mousePosition, setMousePosition] = useState({ x: 0, y: 0 })
  const containerRef = useRef(null)

  // Track mouse for spotlight effect
  useEffect(() => {
    const handleMouseMove = (e) => {
      if (containerRef.current) {
        setMousePosition({
          x: e.clientX,
          y: e.clientY
        })
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

  const loadSession = useCallback(async (id) => {
    setIsLoading(true)
    try {
      const data = await api.getSession(id)
      setCurrentSession(data)
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
    if (currentSessionId) {
      loadSession(currentSessionId)
    } else {
      setCurrentSession(null)
    }
  }, [currentSessionId, loadSession])

  useEffect(() => {
    const timeoutIds = Object.entries(debouncedNoteChanges).map(([paperId, content]) => {
      return setTimeout(async () => {
        try {
          await api.updateNote(paperId, content)
        } catch (error) {
          console.error('Error saving note:', error)
        }
      }, 800)
    })
    return () => timeoutIds.forEach(id => clearTimeout(id))
  }, [debouncedNoteChanges])

  const handleSelectSession = (id) => {
    setCurrentSessionId(id)
    navigate(`/dashboard/${id}`)
  }

  const handleNoteChange = (paperId, content) => {
    setDebouncedNoteChanges(prev => ({ ...prev, [paperId]: content }))
  }

  const handleSynthesize = async (paperIds) => {
    if (!currentSessionId || paperIds.length < 2) return
    try {
      const result = await api.synthesize(currentSessionId, paperIds)
      alert('Synthesis:\n\n' + result.content)
    } catch (error) {
      console.error('Synthesis error:', error)
      alert('Error generating synthesis: ' + error.message)
    }
  }

  const analysisMap = currentSession?.analyses?.reduce((acc, a) => {
    acc[a.analysis_type] = a.data_json
    return acc
  }, {}) || null

  const tabs = [
    { id: 'papers', label: 'Papers', icon: '📄' },
    { id: 'analysis', label: 'Analysis', icon: '📊' },
    { id: 'citations', label: 'Citations', icon: '🔗' },
    { id: 'summary', label: 'Summary', icon: '✨' },
    { id: 'conflicts', label: 'Conflicts', icon: '⚠️' }
  ]

  const renderTabContent = () => {
    if (isLoading) {
      return (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="loading-container"
        >
          <motion.div 
            className="loading-spinner"
            variants={glowVariants}
            animate="glow"
          />
          <p>Loading session...</p>
        </motion.div>
      )
    }

    if (!currentSession) {
      return (
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          className="empty-state"
        >
          <motion.div
            variants={pulseVariants}
            animate="pulse"
            className="empty-icon"
          >
            📚
          </motion.div>
          <p>Select a session from the sidebar to view details</p>
        </motion.div>
      )
    }

    return (
      <AnimatePresence mode="wait">
        <motion.div
          key={activeTab}
          variants={tabContentVariants}
          initial="hidden"
          animate="visible"
          exit="exit"
        >
          {activeTab === 'papers' && (
            <motion.div
              variants={containerVariants}
              initial="hidden"
              animate="visible"
              className="papers-grid"
            >
              {currentSession.papers.map((paper, index) => (
                <motion.div
                  key={paper.id}
                  variants={itemVariants}
                  whileHover={{ 
                    scale: 1.01, 
                    y: -4,
                    transition: { type: "spring", stiffness: 300 }
                  }}
                  className="paper-wrapper"
                >
                  <PaperCard
                    paper={paper}
                    showNotes={true}
                    onNoteChange={handleNoteChange}
                  />
                </motion.div>
              ))}
              {currentSession.papers.length === 0 && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="empty-papers"
                >
                  <span className="empty-papers-icon">📭</span>
                  <p>No papers in this session</p>
                </motion.div>
              )}
            </motion.div>
          )}
          {activeTab === 'analysis' && <AnalysisCharts analysis={analysisMap} />}
          {activeTab === 'citations' && <CitationPanel papers={currentSession.papers} sessionId={currentSessionId} />}
          {activeTab === 'summary' && <SummaryPanel papers={currentSession.papers} sessionId={currentSessionId} onSynthesize={handleSynthesize} />}
          {activeTab === 'conflicts' && currentSessionId && <ConflictsPanel sessionId={currentSessionId} />}
        </motion.div>
      </AnimatePresence>
    )
  }

  return (
    <div ref={containerRef} className="dashboard-container">
      {/* Animated background spotlight */}
      <motion.div
        className="spotlight"
        animate={{
          left: mousePosition.x,
          top: mousePosition.y
        }}
        transition={{ type: "spring", damping: 30, stiffness: 200 }}
      />

      {/* Floating particles */}
      <div className="particles">
        {[...Array(30)].map((_, i) => (
          <motion.div
            key={i}
            className="particle"
            animate={{
              y: [0, -50, 0],
              x: [0, Math.random() * 20 - 10, 0],
              opacity: [0.1, 0.6, 0.1],
              scale: [0.8, 1.2, 0.8]
            }}
            transition={{
              duration: 4 + Math.random() * 3,
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

      {/* Sidebar */}
      <motion.aside
        initial={{ x: -100, opacity: 0 }}
        animate={{ x: 0, opacity: 1 }}
        transition={{ type: "spring", stiffness: 100, damping: 20 }}
        className="sidebar"
      >
        <motion.div 
          className="sidebar-glow"
          animate={{
            opacity: [0.3, 0.5, 0.3]
          }}
          transition={{
            duration: 4,
            repeat: Infinity,
            ease: "easeInOut"
          }}
        />
        <SessionSidebar
          sessions={sessions}
          currentSessionId={currentSessionId}
          onSelectSession={handleSelectSession}
        />
      </motion.aside>

      {/* Main Content */}
      <main className="main-content">
        <AnimatePresence mode="wait">
          {currentSession ? (
            <motion.div
              key={currentSession.id}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              transition={{ duration: 0.4 }}
            >
              {/* Header */}
              <motion.header
                className="session-header"
                whileHover={{ 
                  scale: 1.005,
                  boxShadow: "0 0 60px rgba(220, 38, 38, 0.2)"
                }}
                transition={{ type: "spring", stiffness: 300 }}
              >
                <motion.div 
                  className="header-glow"
                  animate={{
                    scale: [1, 1.2, 1],
                    opacity: [0.5, 0.8, 0.5]
                  }}
                  transition={{
                    duration: 3,
                    repeat: Infinity,
                    ease: "easeInOut"
                  }}
                />
                <div className="header-content">
                  <motion.h1
                    className="session-title"
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.2 }}
                  >
                    {currentSession.name}
                  </motion.h1>
                  <motion.p
                    className="session-query"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: 0.3 }}
                  >
                    <span className="query-icon">🔍</span>
                    {currentSession.query}
                  </motion.p>
                </div>
                <div className="header-stats">
                  <motion.div
                    className="stat-badge"
                    whileHover={{ 
                      scale: 1.1,
                      boxShadow: "0 0 40px rgba(220, 38, 38, 0.4)"
                    }}
                    whileTap={{ scale: 0.95 }}
                  >
                    <span className="stat-number">{currentSession.papers?.length || 0}</span>
                    <span className="stat-label">Papers</span>
                  </motion.div>
                </div>
              </motion.header>

              {/* Tabs */}
              <motion.nav
                className="tabs-container"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.3 }}
              >
                {tabs.map((tab, index) => (
                  <motion.button
                    key={tab.id}
                    onClick={() => setActiveTab(tab.id)}
                    className={`tab-button ${activeTab === tab.id ? 'active' : ''}`}
                    whileHover={{ 
                      scale: 1.05, 
                      y: -2,
                    }}
                    whileTap={{ scale: 0.98 }}
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.1 * index }}
                  >
                    <span className="tab-icon">{tab.icon}</span>
                    <span className="tab-label">{tab.label}</span>
                    {tab.id === 'papers' && currentSession.papers && (
                      <motion.span 
                        className="tab-count"
                        initial={{ scale: 0 }}
                        animate={{ scale: 1 }}
                        transition={{ type: "spring", stiffness: 500, delay: 0.5 }}
                      >
                        {currentSession.papers.length}
                      </motion.span>
                    )}
                    {activeTab === tab.id && (
                      <motion.div
                        className="tab-indicator"
                        layoutId="activeTab"
                        transition={{ type: "spring", stiffness: 500, damping: 30 }}
                      />
                    )}
                  </motion.button>
                ))}
              </motion.nav>

              {/* Content Panel */}
              <motion.section
                className="content-panel"
                initial={{ opacity: 0, scale: 0.98 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: 0.4 }}
              >
                <motion.div 
                  className="content-glow"
                  animate={{
                    opacity: [0.4, 0.7, 0.4]
                  }}
                  transition={{
                    duration: 5,
                    repeat: Infinity,
                    ease: "easeInOut"
                  }}
                />
                {renderTabContent()}
              </motion.section>
            </motion.div>
          ) : (
            <motion.div
              key="empty"
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.9 }}
              className="welcome-panel"
            >
              <motion.div 
                className="welcome-glow"
                animate={{
                  scale: [1, 1.3, 1],
                  opacity: [0.4, 0.8, 0.4]
                }}
                transition={{
                  duration: 3,
                  repeat: Infinity,
                  ease: "easeInOut"
                }}
              />
              <motion.div
                className="welcome-icon"
                animate={{
                  y: [0, -15, 0],
                  rotateY: [0, 360]
                }}
                transition={{
                  y: { duration: 2.5, repeat: Infinity, ease: "easeInOut" },
                  rotateY: { duration: 6, repeat: Infinity, ease: "linear" }
                }}
              >
                📚
              </motion.div>
              <motion.h2 
                className="welcome-title"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.2 }}
              >
                Welcome to Research Hub
              </motion.h2>
              <motion.p 
                className="welcome-subtitle"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.4 }}
              >
                Select a session from the sidebar
              </motion.p>
              <motion.div
                className="welcome-hint"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.6 }}
              >
                <motion.span 
                  className="hint-arrow"
                  animate={{
                    x: [0, -10, 0]
                  }}
                  transition={{
                    duration: 1.5,
                    repeat: Infinity,
                    ease: "easeInOut"
                  }}
                >
                  ←
                </motion.span>
                <span>Or start a new search</span>
              </motion.div>
            </motion.div>
          )}
        </AnimatePresence>
      </main>
    </div>
  )
}

export default Dashboard
