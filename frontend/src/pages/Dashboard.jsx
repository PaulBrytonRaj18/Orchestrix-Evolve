import React, { useState, useEffect, useCallback } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { api } from '../api.js'
import SessionSidebar from '../components/SessionSidebar.jsx'
import PaperCard from '../components/PaperCard.jsx'
import AnalysisCharts from '../components/AnalysisCharts.jsx'
import CitationPanel from '../components/CitationPanel.jsx'
import SummaryPanel from '../components/SummaryPanel.jsx'
import ConflictsPanel from '../components/ConflictsPanel.jsx'
import { FileText, BarChart3, Link2, Sparkles, AlertTriangle, Plus, Clock, Loader2 } from 'lucide-react'

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

function Dashboard() {
  const navigate = useNavigate()
  const { sessionId: urlSessionId } = useParams()
  const [sessions, setSessions] = useState([])
  const [currentSessionId, setCurrentSessionId] = useState(urlSessionId || null)
  const [currentSession, setCurrentSession] = useState(null)
  const [activeTab, setActiveTab] = useState('papers')
  const [debouncedNoteChanges, setDebouncedNoteChanges] = useState({})
  const [isLoading, setIsLoading] = useState(false)

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
      await api.synthesize(currentSessionId, paperIds)
    } catch (error) {
      console.error('Synthesis error:', error)
    }
  }

  const analysisMap = currentSession?.analyses?.reduce((acc, a) => {
    acc[a.analysis_type] = a.data_json
    return acc
  }, {}) || null

  const tabs = [
    { id: 'papers', label: 'Papers', icon: FileText },
    { id: 'analysis', label: 'Analysis', icon: BarChart3 },
    { id: 'citations', label: 'Citations', icon: Link2 },
    { id: 'summary', label: 'Summary', icon: Sparkles },
    { id: 'conflicts', label: 'Conflicts', icon: AlertTriangle }
  ]

  const formatDate = (dateString) => {
    const date = new Date(dateString)
    const now = new Date()
    const diff = now - date
    const days = Math.floor(diff / (1000 * 60 * 60 * 24))
    
    if (days === 0) return 'Today'
    if (days === 1) return 'Yesterday'
    if (days < 7) return `${days} days ago`
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
  }

  return (
    <div style={{ display: 'flex', gap: 'var(--space-6)', minHeight: 'calc(100vh - var(--nav-height) - 100px)' }}>
      {/* Sidebar */}
      <div className="dashboard-sidebar">
        <div style={{ marginBottom: 'var(--space-4)' }}>
          <h2 style={{ fontSize: 'var(--text-sm)', fontWeight: 'var(--font-semibold)', color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.05em', padding: '0 var(--space-2)', marginBottom: 'var(--space-2)' }}>
            Recent Sessions
          </h2>
          <SessionSidebar
            sessions={sessions}
            currentSessionId={currentSessionId}
            onSelectSession={handleSelectSession}
          />
        </div>

        {sessions.length === 0 && (
          <div style={{ padding: 'var(--space-4)', textAlign: 'center' }}>
            <p style={{ fontSize: 'var(--text-sm)', color: 'var(--text-tertiary)', marginBottom: 'var(--space-3)' }}>
              No sessions yet
            </p>
            <button
              onClick={() => navigate('/')}
              className="btn btn-primary btn-sm"
            >
              <Plus size={14} />
              Start searching
            </button>
          </div>
        )}
      </div>

      {/* Main Content */}
      <div className="dashboard-main">
        {isLoading ? (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: 'var(--space-16)' }}>
            <Loader2 size={24} style={{ animation: 'spin 0.8s linear infinite', color: 'var(--text-tertiary)', marginBottom: 'var(--space-4)' }} />
            <p style={{ color: 'var(--text-secondary)' }}>Loading session...</p>
          </div>
        ) : currentSession ? (
          <motion.div
            key={currentSession.id}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3 }}
          >
            {/* Session Header */}
            <div style={{ marginBottom: 'var(--space-6)' }}>
              <h1 style={{ fontSize: 'var(--text-2xl)', fontWeight: 'var(--font-bold)', marginBottom: 'var(--space-2)' }}>
                {currentSession.name}
              </h1>
              <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-4)', color: 'var(--text-secondary)', fontSize: 'var(--text-sm)' }}>
                <span style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-1)' }}>
                  <Clock size={14} />
                  {formatDate(currentSession.created_at)}
                </span>
                <span style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-1)' }}>
                  <FileText size={14} />
                  {currentSession.papers?.length || 0} papers
                </span>
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
                    {tab.id === 'papers' && currentSession.papers && (
                      <span className="tab-count">{currentSession.papers.length}</span>
                    )}
                  </button>
                )
              })}
            </div>

            {/* Content */}
            <AnimatePresence mode="wait">
              <motion.div
                key={activeTab}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.2 }}
              >
                {activeTab === 'papers' && (
                  <motion.div
                    variants={containerVariants}
                    initial="hidden"
                    animate="visible"
                    className="papers-grid"
                  >
                    {currentSession.papers.map((paper) => (
                      <motion.div key={paper.id} variants={itemVariants}>
                        <PaperCard
                          paper={paper}
                          showNotes={true}
                          onNoteChange={handleNoteChange}
                        />
                      </motion.div>
                    ))}
                    {currentSession.papers.length === 0 && (
                      <div className="empty-state">
                        <div className="empty-icon">
                          <FileText size={32} strokeWidth={1} />
                        </div>
                        <h3 className="empty-title">No papers yet</h3>
                        <p className="empty-description">
                          Start a new search to add papers to this session
                        </p>
                      </div>
                    )}
                  </motion.div>
                )}
                {activeTab === 'analysis' && <AnalysisCharts analysis={analysisMap} />}
                {activeTab === 'citations' && <CitationPanel papers={currentSession.papers} sessionId={currentSessionId} />}
                {activeTab === 'summary' && <SummaryPanel papers={currentSession.papers} sessionId={currentSessionId} onSynthesize={handleSynthesize} />}
                {activeTab === 'conflicts' && currentSessionId && <ConflictsPanel sessionId={currentSessionId} />}
              </motion.div>
            </AnimatePresence>
          </motion.div>
        ) : (
          <div className="welcome-panel">
            <div className="empty-icon" style={{ marginBottom: 'var(--space-4)' }}>
              <FileText size={48} strokeWidth={1} />
            </div>
            <h2 className="welcome-title">Select a session</h2>
            <p className="welcome-description">
              Choose a session from the sidebar to view papers and analysis
            </p>
            <button
              onClick={() => navigate('/')}
              className="btn btn-primary"
              style={{ marginTop: 'var(--space-4)' }}
            >
              <Plus size={16} />
              New Search
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

export default Dashboard
