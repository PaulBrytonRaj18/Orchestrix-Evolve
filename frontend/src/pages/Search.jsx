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
import { Search as SearchIcon, FileText, BarChart3, Link2, Sparkles, AlertTriangle, Map, Loader2, ArrowRight } from 'lucide-react'

const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { staggerChildren: 0.08 }
  }
}

const itemVariants = {
  hidden: { opacity: 0, y: 12 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.3, ease: 'easeOut' }
  }
}

function Search() {
  const navigate = useNavigate()
  const inputRef = useRef(null)
  const [query, setQuery] = useState('')
  const [isSearching, setIsSearching] = useState(false)
  const [currentSessionId, setCurrentSessionId] = useState(null)
  const [trace, setTrace] = useState([])
  const [papers, setPapers] = useState([])
  const [analysis, setAnalysis] = useState(null)
  const [roadmap, setRoadmap] = useState(null)
  const [activeTab, setActiveTab] = useState('papers')
  const [pollingInterval, setPollingInterval] = useState(null)

  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  const handleSearch = async (e) => {
    e?.preventDefault()
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
      if (pollingInterval) clearInterval(pollingInterval)
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
    } catch (error) {
      console.error('Synthesis error:', error)
    }
  }

  const handleRoadmapQueryClick = async (query) => {
    setIsSearching(true)
    try {
      const response = await fetch(`/sessions/${currentSessionId}/roadmap/query?query=${encodeURIComponent(query)}`, { method: 'POST' })
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
    { id: 'papers', label: 'Papers', icon: FileText },
    { id: 'analysis', label: 'Analysis', icon: BarChart3 },
    { id: 'citations', label: 'Citations', icon: Link2 },
    { id: 'summary', label: 'Summary', icon: Sparkles },
    { id: 'conflicts', label: 'Conflicts', icon: AlertTriangle },
    { id: 'roadmap', label: 'Roadmap', icon: Map }
  ]

  const suggestions = [
    'Machine learning transformers',
    'Quantum computing algorithms',
    'CRISPR gene editing',
    'Climate change mitigation'
  ]

  return (
    <div style={{ maxWidth: '1000px', margin: '0 auto', paddingTop: 'var(--space-16)' }}>
      {/* Hero Search */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        style={{ textAlign: 'center', marginBottom: 'var(--space-12)' }}
      >
        <h1 style={{ fontSize: 'var(--text-4xl)', fontWeight: 'var(--font-bold)', marginBottom: 'var(--space-3)', letterSpacing: '-0.02em' }}>
          Research smarter, not harder
        </h1>
        <p style={{ fontSize: 'var(--text-lg)', color: 'var(--text-secondary)', marginBottom: 'var(--space-8)', maxWidth: '500px', margin: '0 auto var(--space-8)' }}>
          AI-powered research intelligence platform
        </p>

        <form onSubmit={handleSearch} className="search-container">
          <div className="search-bar">
            <div className="search-icon">
              <SearchIcon strokeWidth={1.75} />
            </div>
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search for research topics, papers, or questions..."
              disabled={isSearching}
              className="search-input"
            />
            <div className="search-actions">
              <button
                type="submit"
                disabled={isSearching || !query.trim()}
                className="btn btn-primary search-btn"
              >
                {isSearching ? (
                  <>
                    <Loader2 size={16} style={{ animation: 'spin 0.8s linear infinite' }} />
                    Searching
                  </>
                ) : (
                  <>
                    Search
                    <ArrowRight size={16} />
                  </>
                )}
              </button>
            </div>
          </div>
        </form>

        {/* Suggestions */}
        {!isSearching && papers.length === 0 && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.3 }}
            style={{ marginTop: 'var(--space-6)' }}
          >
            <p style={{ fontSize: 'var(--text-sm)', color: 'var(--text-tertiary)', marginBottom: 'var(--space-3)' }}>
              Try searching for:
            </p>
            <div style={{ display: 'flex', gap: 'var(--space-2)', justifyContent: 'center', flexWrap: 'wrap' }}>
              {suggestions.map((suggestion) => (
                <button
                  key={suggestion}
                  onClick={() => setQuery(suggestion)}
                  className="btn btn-ghost btn-sm"
                  style={{ borderRadius: 'var(--radius-full)' }}
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </motion.div>
        )}
      </motion.div>

      {/* Agent Activity */}
      <AnimatePresence>
        {isSearching && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.3 }}
            style={{ marginBottom: 'var(--space-8)' }}
          >
            <div className="card">
              <div className="card-body">
                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', marginBottom: 'var(--space-4)' }}>
                  <div className="status-dot online" />
                  <span style={{ fontSize: 'var(--text-sm)', fontWeight: 'var(--font-medium)' }}>Agents are working...</span>
                </div>
                <AgentTraceLog trace={trace} />
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Results */}
      <AnimatePresence>
        {papers.length > 0 && !isSearching && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            transition={{ duration: 0.3 }}
          >
            {/* Results Header */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 'var(--space-6)' }}>
              <div>
                <h2 style={{ fontSize: 'var(--text-xl)', fontWeight: 'var(--font-semibold)', marginBottom: 'var(--space-1)' }}>
                  {query}
                </h2>
                <p style={{ fontSize: 'var(--text-sm)', color: 'var(--text-secondary)' }}>
                  {papers.length} papers found
                </p>
              </div>
            </div>

            {/* Tabs */}
            <div className="tabs" style={{ marginBottom: 'var(--space-6)' }}>
              {tabs.map((tab) => {
                const Icon = tab.icon
                const isActive = activeTab === tab.id
                return (
                  <button
                    key={tab.id}
                    onClick={() => setActiveTab(tab.id)}
                    className={`tab ${isActive ? 'active' : ''}`}
                  >
                    <Icon size={16} strokeWidth={1.75} />
                    <span>{tab.label}</span>
                    {tab.id === 'papers' && (
                      <span className="tab-count">{papers.length}</span>
                    )}
                  </button>
                )
              })}
            </div>

            {/* Tab Content */}
            <motion.div
              key={activeTab}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.2 }}
            >
              {activeTab === 'papers' && (
                <motion.div
                  variants={containerVariants}
                  initial="hidden"
                  animate="visible"
                  className="papers-grid"
                >
                  {papers.map((paper) => (
                    <motion.div key={paper.id} variants={itemVariants}>
                      <PaperCard
                        paper={paper}
                        onCopyCitation={handleCopyCitation}
                      />
                    </motion.div>
                  ))}
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
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

export default Search
