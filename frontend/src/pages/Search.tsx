import React, { useState, useEffect, useRef, lazy, Suspense } from 'react'
import { m, AnimatePresence } from 'framer-motion'
import { api, streamJob } from '../api'
import { useToast } from '../contexts/ToastContext'
import AgentTraceLog from '../components/AgentTraceLog'
import PaperCard from '../components/PaperCard'
import CitationPanel from '../components/CitationPanel'
import SummaryPanel from '../components/SummaryPanel'
import ConflictsPanel from '../components/ConflictsPanel'
import RoadmapPanel from '../components/RoadmapPanel'
import { Search as SearchIcon, FileText, BarChart3, Link2, Sparkles, AlertTriangle, Map, Loader2, ArrowRight, Network, MessageSquare } from 'lucide-react'
import type {
  AgentTrace,
  PaperWithDetails,
  AnalysisData,
  RoadmapResponse,
  PaperPreview,
  OrchestrateResponse,
  JobCreate,
} from '../types/api'

// recharts (~100 kB gzipped) loads only when the Analysis tab is opened.
const AnalysisCharts = lazy(() => import('../components/AnalysisCharts'))
const CitationGraph = lazy(() => import('../components/CitationGraph'))
const AskPanel = lazy(() => import('../components/AskPanel'))

/** Streamed previews have no stored metadata yet; give them the shape the cards expect. */
function previewToPaper(p: PaperPreview, sessionId: string): PaperWithDetails {
  const now = new Date().toISOString()
  return {
    ...p,
    authors: p.authors ?? [],
    session_id: sessionId,
    created_at: now,
    updated_at: now,
    summary: null,
    citation: null,
    notes: [],
  }
}

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
    transition: { duration: 0.3, ease: 'easeOut' as const }
  }
}

function Search() {
  const { showToast } = useToast()
  const inputRef = useRef<HTMLInputElement>(null)
  const [query, setQuery] = useState('')
  const [isSearching, setIsSearching] = useState(false)
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null)
  const [trace, setTrace] = useState<AgentTrace[]>([])
  const [papers, setPapers] = useState<PaperWithDetails[]>([])
  const [analysis, setAnalysis] = useState<AnalysisData | null>(null)
  const [roadmap, setRoadmap] = useState<RoadmapResponse | null>(null)
  const [activeTab, setActiveTab] = useState<string>('papers')
  const [deep, setDeep] = useState(false)
  const streamRef = useRef<AbortController | null>(null)

  useEffect(() => {
    inputRef.current?.focus()
    return () => streamRef.current?.abort() // stop following the job when leaving the page
  }, [])

  /** Start a background job and follow its event stream until it finishes. */
  const runJob = async (sessionId: string, body: JobCreate = {}) => {
    streamRef.current?.abort()
    const controller = new AbortController()
    streamRef.current = controller
    const job = await api.startJob(sessionId, body)
    if (job.trace?.length) setTrace(job.trace)
    await new Promise<void>((resolve) => {
      streamJob(
        job.id,
        {
          onTrace: setTrace,
          onPapers: (preview) => {
            // Ranked papers arrive seconds before summaries; show them right away.
            if (body.kind !== 'followup') setPapers(preview.map((p) => previewToPaper(p, sessionId)))
          },
          onDone: (result: OrchestrateResponse) => {
            setTrace(result.trace || [])
            setPapers(result.papers || []) // the whole session, with stored ids
            if (result.analysis) setAnalysis(result.analysis)
            if (result.roadmap) setRoadmap(result.roadmap)
            resolve()
          },
          onError: (message) => {
            showToast(message, 'error')
            resolve()
          },
        },
        controller.signal,
      ).finally(resolve)
    })
  }

  const handleSearch = async (e?: React.FormEvent) => {
    e?.preventDefault()
    if (!query.trim()) return

    setIsSearching(true)
    setActiveTab('papers')
    setTrace([])
    setPapers([])
    setAnalysis(null)
    setRoadmap(null)

    const sessionName = query.slice(0, 40) + '_' + Date.now()
    try {
      const session = await api.createSession(sessionName, query)
      setCurrentSessionId(session.id)
      await runJob(session.id, deep ? { kind: 'deep' } : {})
    } catch (error) {
      showToast(error instanceof Error ? error.message : 'Search failed', 'error')
    } finally {
      setIsSearching(false)
    }
  }

  useEffect(() => {
    const fetchRoadmap = async () => {
      if (activeTab === 'roadmap' && currentSessionId && !roadmap && !isSearching) {
        try {
          const roadmapData = await api.getRoadmap(currentSessionId)
          setRoadmap(roadmapData)
        } catch {
          console.log('No roadmap found or error fetching roadmap')
        }
      }
    }
    fetchRoadmap()
  }, [activeTab, currentSessionId, roadmap, isSearching])

  const handleCopyCitation = (citation: string) => {
    navigator.clipboard.writeText(citation)
  }

  const handleSynthesize = async (paperIds: string[]) => {
    if (!currentSessionId || paperIds.length < 2) return
    try {
      await api.synthesize(currentSessionId, paperIds)
      showToast('Synthesis complete', 'success')
    } catch (error) {
      showToast(error instanceof Error ? error.message : 'Synthesis failed', 'error')
    }
  }

  const handleRoadmapQueryClick = async (followUp: string) => {
    if (!currentSessionId) return
    setIsSearching(true)
    setActiveTab('papers')
    try {
      await runJob(currentSessionId, { kind: 'followup', query: followUp })
      showToast(`Added results for "${followUp}"`, 'success')
    } catch (error) {
      showToast(error instanceof Error ? error.message : 'Roadmap query failed', 'error')
    } finally {
      setIsSearching(false)
    }
  }

  const tabs: Array<{ id: string; label: string; icon: React.ElementType }> = [
    { id: 'papers', label: 'Papers', icon: FileText },
    { id: 'analysis', label: 'Analysis', icon: BarChart3 },
    { id: 'citations', label: 'Citations', icon: Link2 },
    { id: 'summary', label: 'Summary', icon: Sparkles },
    { id: 'conflicts', label: 'Conflicts', icon: AlertTriangle },
    { id: 'roadmap', label: 'Roadmap', icon: Map },
    { id: 'graph', label: 'Graph', icon: Network },
    { id: 'ask', label: 'Ask', icon: MessageSquare }
  ]

  const suggestions: string[] = [
    'Machine learning transformers',
    'Quantum computing algorithms',
    'CRISPR gene editing',
    'Climate change mitigation'
  ]

  return (
    <div className="search-page">
      {/* Hero Search */}
      <m.div
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
        <label
          style={{ display: 'inline-flex', alignItems: 'center', gap: 'var(--space-2)', marginTop: 'var(--space-3)', fontSize: 'var(--text-sm)', color: 'var(--text-secondary)' }}
          title="Searches in rounds, following up on what it finds, until new rounds stop adding papers"
        >
          <input type="checkbox" checked={deep} onChange={(e) => setDeep(e.target.checked)} disabled={isSearching} />
          Deep research (several rounds of follow-up searches)
        </label>

        {/* Suggestions */}
        {!isSearching && papers.length === 0 && (
          <m.div
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
          </m.div>
        )}
      </m.div>

      {/* Agent Activity */}
      <AnimatePresence>
        {isSearching && (
          <m.div
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
          </m.div>
        )}
      </AnimatePresence>

      {/* Results */}
      <AnimatePresence>
        {papers.length > 0 && (
          <m.div
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
                  {isSearching && ' · summaries and analysis on the way…'}
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
            <m.div
              key={activeTab}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.2 }}
            >
              {activeTab === 'papers' && (
                <m.div
                  variants={containerVariants}
                  initial="hidden"
                  animate="visible"
                  className="papers-grid"
                >
                  {papers.map((paper) => (
                    <m.div key={paper.id} variants={itemVariants}>
                      <PaperCard
                        paper={paper}
                        onCopyCitation={handleCopyCitation}
                        canExplore={!isSearching}
                      />
                    </m.div>
                  ))}
                </m.div>
              )}
              {activeTab === 'analysis' && <Suspense fallback={<div className="loading-spinner" />}><AnalysisCharts analysis={analysis} /></Suspense>}
              {activeTab === 'citations' && <CitationPanel papers={papers} />}
              {activeTab === 'summary' && <SummaryPanel papers={papers} onSynthesize={handleSynthesize} />}
              {activeTab === 'conflicts' && currentSessionId && <ConflictsPanel sessionId={currentSessionId} />}
              {activeTab === 'ask' && currentSessionId && !isSearching && (
                <Suspense fallback={<div className="loading-spinner" />}>
                  <AskPanel sessionId={currentSessionId} />
                </Suspense>
              )}
              {activeTab === 'graph' && currentSessionId && !isSearching && (
                <Suspense fallback={<div className="loading-spinner" />}>
                  <CitationGraph sessionId={currentSessionId} onSearch={handleRoadmapQueryClick} />
                </Suspense>
              )}
              {activeTab === 'roadmap' && currentSessionId && (
                <RoadmapPanel
                  roadmap={roadmap}
                  sessionId={currentSessionId}
                  onQueryClick={handleRoadmapQueryClick}
                  onRefresh={async () => {
                    try {
                      const data = await api.getRoadmap(currentSessionId);
                      setRoadmap(data);
                    } catch {
                      setRoadmap(null);
                    }
                  }}
                />
              )}
            </m.div>
          </m.div>
        )}
      </AnimatePresence>
    </div>
  )
}

export default Search
