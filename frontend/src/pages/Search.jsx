import React, { useState, useEffect, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { api } from '../api.js'
import AgentTraceLog from '../components/AgentTraceLog.jsx'
import PaperCard from '../components/PaperCard.jsx'
import AnalysisCharts from '../components/AnalysisCharts.jsx'
import CitationPanel from '../components/CitationPanel.jsx'
import SummaryPanel from '../components/SummaryPanel.jsx'
import ConflictsPanel from '../components/ConflictsPanel.jsx'
import RoadmapPanel from '../components/RoadmapPanel.jsx'

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

function Search() {
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const [isSearching, setIsSearching] = useState(false)
  const [currentSessionId, setCurrentSessionId] = useState(null)
  const [trace, setTrace] = useState([])
  const [papers, setPapers] = useState([])
  const [analysis, setAnalysis] = useState(null)
  const [roadmap, setRoadmap] = useState(null)
  const [activeTab, setActiveTab] = useState('papers')
  const [pollingInterval, setPollingInterval] = useState(null)
  const [mousePosition, setMousePosition] = useState({ x: 0, y: 0 })
  const containerRef = useRef(null)

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

  const handleSearch = async (e) => {
    e.preventDefault()
    if (!query.trim()) return

    setIsSearching(true)
    setActiveTab('papers')
    setTrace([])
    setPapers([])
    setAnalysis(null)

    const timestamp = Date.now()
    const sessionName = query.slice(0, 40) + '_' + timestamp

    try {
      const session = await api.createSession(sessionName, query)
      setCurrentSessionId(session.id)

      const result = await api.orchestrate(session.id)
      setTrace(result.trace || [])
      setPapers(result.papers || [])
      setAnalysis(result.analysis || null)
      setRoadmap(result.roadmap || null)

    } catch (error) {
      console.error('Search error:', error)
      alert('Error running search: ' + error.message)
    } finally {
      setIsSearching(false)
    }
  }

  const pollForUpdates = useCallback(async () => {
    if (!currentSessionId) return

    try {
      const session = await api.getSession(currentSessionId)
      if (session.papers && session.papers.length > 0) {
        setPapers(session.papers)
      }

      const doneEntry = trace.find(e => e.agent === 'Citations & Summaries' && e.status === 'done')
      if (doneEntry) {
        clearInterval(pollingInterval)
        setPollingInterval(null)
      }
    } catch (error) {
      console.error('Polling error:', error)
    }
  }, [currentSessionId, pollingInterval, trace])

  useEffect(() => {
    if (currentSessionId && isSearching) {
      const interval = setInterval(pollForUpdates, 1500)
      setPollingInterval(interval)
      return () => clearInterval(interval)
    }
  }, [currentSessionId, isSearching, pollForUpdates])

  useEffect(() => {
    return () => {
      if (pollingInterval) {
        clearInterval(pollingInterval)
      }
    }
  }, [pollingInterval])

  useEffect(() => {
    const fetchRoadmap = async () => {
      if (activeTab === 'roadmap' && currentSessionId && !roadmap) {
        try {
          const roadmapData = await api.getRoadmap(currentSessionId)
          setRoadmap(roadmapData)
        } catch (error) {
          console.log('No roadmap found or error fetching roadmap')
        }
      }
    }
    fetchRoadmap()
  }, [activeTab, currentSessionId, roadmap])

  const handleCopyCitation = (citation) => {
    navigator.clipboard.writeText(citation)
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

  const handleRoadmapQueryClick = async (query) => {
    setIsSearching(true)
    try {
      const response = await fetch(
        `/sessions/${currentSessionId}/roadmap/query?query=${encodeURIComponent(query)}`,
        { method: 'POST' }
      )
      const data = await response.json()
      if (data.orchestration_result) {
        setPapers(prev => [...prev, ...(data.orchestration_result.papers || [])])
        setAnalysis(data.orchestration_result.analysis)
      }
    } catch (error) {
      console.error('Error executing roadmap query:', error)
    } finally {
      setIsSearching(false)
    }
  }

  const tabs = [
    { id: 'papers', label: 'Papers', icon: '📄' },
    { id: 'analysis', label: 'Analysis', icon: '📊' },
    { id: 'citations', label: 'Citations', icon: '🔗' },
    { id: 'summary', label: 'Summary', icon: '✨' },
    { id: 'conflicts', label: 'Conflicts', icon: '⚠️' },
    { id: 'roadmap', label: 'Roadmap', icon: '🗺️' }
  ]

  const renderTabContent = () => {
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
              {papers.map((paper, index) => (
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
                    onCopyCitation={handleCopyCitation}
                  />
                </motion.div>
              ))}
              {papers.length === 0 && !isSearching && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="empty-papers"
                >
                  <span className="empty-papers-icon">🔍</span>
                  <p>No papers found. Try a different search query.</p>
                </motion.div>
              )}
            </motion.div>
          )}
          {activeTab === 'analysis' && <AnalysisCharts analysis={analysis} />}
          {activeTab === 'citations' && <CitationPanel papers={papers} sessionId={currentSessionId} />}
          {activeTab === 'summary' && <SummaryPanel papers={papers} sessionId={currentSessionId} onSynthesize={handleSynthesize} />}
          {activeTab === 'conflicts' && currentSessionId && <ConflictsPanel sessionId={currentSessionId} />}
          {activeTab === 'roadmap' && currentSessionId && (
            <RoadmapPanel
              roadmap={roadmap}
              sessionId={currentSessionId}
              onQueryClick={handleRoadmapQueryClick}
            />
          )}
        </motion.div>
      </AnimatePresence>
    )
  }

  return (
    <div ref={containerRef} className="search-container">
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

      {/* Hero Section */}
      <motion.div 
        className="search-hero"
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
      >
        <motion.div 
          className="hero-glow"
          animate={{
            scale: [1, 1.2, 1],
            opacity: [0.4, 0.7, 0.4]
          }}
          transition={{
            duration: 4,
            repeat: Infinity,
            ease: "easeInOut"
          }}
        />
        
        <motion.div
          className="hero-icon"
          animate={{
            y: [0, -10, 0],
            rotateY: [0, 360]
          }}
          transition={{
            y: { duration: 2, repeat: Infinity, ease: "easeInOut" },
            rotateY: { duration: 8, repeat: Infinity, ease: "linear" }
          }}
        >
          🔬
        </motion.div>

        <motion.h1 
          className="search-title"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
        >
          Orchestrix
        </motion.h1>
        
        <motion.p 
          className="search-subtitle"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.4 }}
        >
          Multi-Agent Research Intelligence Platform
        </motion.p>

        {/* Search Form */}
        <motion.form 
          onSubmit={handleSearch} 
          className="search-form"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.5 }}
        >
          <div className="search-input-wrapper">
            <motion.div 
              className="input-glow"
              animate={{
                opacity: [0.3, 0.6, 0.3]
              }}
              transition={{
                duration: 3,
                repeat: Infinity,
                ease: "easeInOut"
              }}
            />
            <span className="search-input-icon">🔍</span>
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Enter research query (e.g., machine learning transformers, quantum computing)..."
              disabled={isSearching}
              className="search-input"
            />
          </div>
          
          <motion.button
            type="submit"
            disabled={isSearching}
            className={`search-button ${isSearching ? 'searching' : ''}`}
            whileHover={{ scale: isSearching ? 1 : 1.02 }}
            whileTap={{ scale: isSearching ? 1 : 0.98 }}
          >
            {isSearching ? (
              <>
                <motion.span 
                  className="button-spinner"
                  animate={{ rotate: 360 }}
                  transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
                />
                Searching...
              </>
            ) : (
              <>
                <span className="button-icon">🚀</span>
                Search
              </>
            )}
          </motion.button>
        </motion.form>
      </motion.div>

      {/* Agent Activity Panel */}
      <AnimatePresence>
        {isSearching && (
          <motion.div 
            className="agent-activity-panel"
            initial={{ opacity: 0, y: 20, height: 0 }}
            animate={{ opacity: 1, y: 0, height: 'auto' }}
            exit={{ opacity: 0, y: -20, height: 0 }}
            transition={{ duration: 0.4 }}
          >
            <motion.div 
              className="panel-glow"
              animate={{
                opacity: [0.3, 0.6, 0.3]
              }}
              transition={{
                duration: 2,
                repeat: Infinity,
                ease: "easeInOut"
              }}
            />
            <div className="panel-header">
              <motion.span 
                className="panel-icon"
                animate={{
                  rotate: [0, 360]
                }}
                transition={{
                  duration: 3,
                  repeat: Infinity,
                  ease: "linear"
                }}
              >
                ⚡
              </motion.span>
              <h3 className="panel-title">Agent Activity</h3>
              <motion.div 
                className="activity-indicator"
                animate={{
                  scale: [1, 1.2, 1],
                  opacity: [0.5, 1, 0.5]
                }}
                transition={{
                  duration: 1,
                  repeat: Infinity,
                  ease: "easeInOut"
                }}
              />
            </div>
            <AgentTraceLog trace={trace} />
          </motion.div>
        )}
      </AnimatePresence>

      {/* Results Section */}
      <AnimatePresence>
        {papers.length > 0 && !isSearching && (
          <motion.div
            className="results-section"
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -30 }}
            transition={{ duration: 0.5 }}
          >
            {/* Results Header */}
            <motion.div 
              className="results-header"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.2 }}
            >
              <motion.div 
                className="results-header-glow"
                animate={{
                  scale: [1, 1.1, 1],
                  opacity: [0.4, 0.7, 0.4]
                }}
                transition={{
                  duration: 3,
                  repeat: Infinity,
                  ease: "easeInOut"
                }}
              />
              <div className="results-info">
                <h2 className="results-title">Search Results</h2>
                <p className="results-query">
                  <span className="query-icon">🔍</span>
                  {query}
                </p>
              </div>
              <motion.div 
                className="results-count"
                whileHover={{ 
                  scale: 1.05,
                  boxShadow: "0 0 30px rgba(220, 38, 38, 0.4)"
                }}
              >
                <span className="count-number">{papers.length}</span>
                <span className="count-label">Papers Found</span>
              </motion.div>
            </motion.div>

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
                  {tab.id === 'papers' && (
                    <motion.span 
                      className="tab-count"
                      initial={{ scale: 0 }}
                      animate={{ scale: 1 }}
                      transition={{ type: "spring", stiffness: 500, delay: 0.5 }}
                    >
                      {papers.length}
                    </motion.span>
                  )}
                  {activeTab === tab.id && (
                    <motion.div
                      className="tab-indicator"
                      layoutId="activeTabSearch"
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
        )}
      </AnimatePresence>

      {/* Empty State when no search */}
      {papers.length === 0 && !isSearching && (
        <motion.div 
          className="search-hints"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.8 }}
        >
          <h3 className="hints-title">Try searching for:</h3>
          <div className="hints-grid">
            {[
              { icon: '🧠', text: 'Machine learning transformers' },
              { icon: '⚛️', text: 'Quantum computing algorithms' },
              { icon: '🧬', text: 'CRISPR gene editing' },
              { icon: '🌍', text: 'Climate change mitigation' }
            ].map((hint, index) => (
              <motion.button
                key={index}
                className="hint-chip"
                onClick={() => setQuery(hint.text)}
                whileHover={{ 
                  scale: 1.05, 
                  y: -2,
                  boxShadow: "0 0 20px rgba(220, 38, 38, 0.3)"
                }}
                whileTap={{ scale: 0.98 }}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.9 + index * 0.1 }}
              >
                <span className="hint-icon">{hint.icon}</span>
                <span className="hint-text">{hint.text}</span>
              </motion.button>
            ))}
          </div>
        </motion.div>
      )}
    </div>
  )
}

export default Search
