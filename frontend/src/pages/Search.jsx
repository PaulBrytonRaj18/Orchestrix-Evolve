import React, { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api.js'
import AgentTraceLog from '../components/AgentTraceLog.jsx'
import PaperCard from '../components/PaperCard.jsx'
import AnalysisCharts from '../components/AnalysisCharts.jsx'
import CitationPanel from '../components/CitationPanel.jsx'
import SummaryPanel from '../components/SummaryPanel.jsx'

function Search() {
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const [isSearching, setIsSearching] = useState(false)
  const [currentSessionId, setCurrentSessionId] = useState(null)
  const [trace, setTrace] = useState([])
  const [papers, setPapers] = useState([])
  const [analysis, setAnalysis] = useState(null)
  const [activeTab, setActiveTab] = useState('papers')
  const [pollingInterval, setPollingInterval] = useState(null)

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

  const handleCopyCitation = (citation) => {
    navigator.clipboard.writeText(citation)
    alert('Citation copied to clipboard!')
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

  const renderTabContent = () => {
    switch (activeTab) {
      case 'papers':
        return (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            {papers.map((paper) => (
              <PaperCard
                key={paper.id}
                paper={paper}
                onCopyCitation={handleCopyCitation}
              />
            ))}
            {papers.length === 0 && !isSearching && (
              <div style={{ color: '#64748b', fontStyle: 'italic', textAlign: 'center', padding: '2rem' }}>
                No papers found. Try a different search query.
              </div>
            )}
          </div>
        )
      case 'analysis':
        return <AnalysisCharts analysis={analysis} />
      case 'citations':
        return <CitationPanel papers={papers} sessionId={currentSessionId} />
      case 'summary':
        return <SummaryPanel papers={papers} sessionId={currentSessionId} onSynthesize={handleSynthesize} />
      default:
        return null
    }
  }

  return (
    <div style={{ maxWidth: '1200px', margin: '0 auto' }}>
      <div style={{ textAlign: 'center', marginBottom: '3rem' }}>
        <h1 style={{ fontSize: '2.5rem', color: '#f1f5f9', marginBottom: '0.5rem' }}>
          Orchestrix
        </h1>
        <p style={{ color: '#94a3b8', fontSize: '1.1rem', marginBottom: '2rem' }}>
          Multi-Agent Research Intelligence Platform
        </p>

        <form onSubmit={handleSearch} style={{ maxWidth: '600px', margin: '0 auto' }}>
          <div style={{ display: 'flex', gap: '0.75rem' }}>
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Enter research query (e.g., machine learning transformers, quantum computing algorithms)..."
              disabled={isSearching}
              style={{
                flex: 1,
                padding: '1rem 1.5rem',
                fontSize: '1rem',
                background: '#1e293b',
                border: '2px solid #334155',
                borderRadius: '12px',
                color: '#e2e8f0',
                outline: 'none'
              }}
              onFocus={(e) => e.target.style.borderColor = '#60a5fa'}
              onBlur={(e) => e.target.style.borderColor = '#334155'}
            />
            <button
              type="submit"
              disabled={isSearching}
              style={{
                padding: '1rem 2rem',
                fontSize: '1rem',
                background: isSearching ? '#334155' : '#60a5fa',
                color: isSearching ? '#64748b' : '#0f172a',
                border: 'none',
                borderRadius: '12px',
                cursor: isSearching ? 'not-allowed' : 'pointer',
                fontWeight: '600'
              }}
            >
              {isSearching ? 'Searching...' : 'Search'}
            </button>
          </div>
        </form>
      </div>

      {isSearching && (
        <div style={{
          background: '#1e293b',
          padding: '1.5rem',
          borderRadius: '12px',
          marginBottom: '2rem',
          border: '1px solid #334155'
        }}>
          <h3 style={{ color: '#f1f5f9', marginBottom: '1rem' }}>Agent Activity</h3>
          <AgentTraceLog trace={trace} />
        </div>
      )}

      {papers.length > 0 && !isSearching && (
        <>
          <div style={{
            display: 'flex',
            gap: '0.5rem',
            marginBottom: '1.5rem',
            borderBottom: '1px solid #334155',
            paddingBottom: '0.5rem'
          }}>
            {['papers', 'analysis', 'citations', 'summary'].map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                style={{
                  padding: '0.75rem 1.5rem',
                  background: 'transparent',
                  border: 'none',
                  borderBottom: activeTab === tab ? '2px solid #60a5fa' : '2px solid transparent',
                  color: activeTab === tab ? '#60a5fa' : '#94a3b8',
                  cursor: 'pointer',
                  fontWeight: activeTab === tab ? '600' : '400',
                  textTransform: 'capitalize'
                }}
              >
                {tab} {tab === 'papers' && `(${papers.length})`}
              </button>
            ))}
          </div>

          {renderTabContent()}
        </>
      )}
    </div>
  )
}

export default Search
