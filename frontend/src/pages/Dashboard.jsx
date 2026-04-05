import React, { useState, useEffect, useCallback } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from '../api.js'
import SessionSidebar from '../components/SessionSidebar.jsx'
import PaperCard from '../components/PaperCard.jsx'
import AnalysisCharts from '../components/AnalysisCharts.jsx'
import CitationPanel from '../components/CitationPanel.jsx'
import SummaryPanel from '../components/SummaryPanel.jsx'

function Dashboard() {
  const navigate = useNavigate()
  const { sessionId: urlSessionId } = useParams()
  const [sessions, setSessions] = useState([])
  const [currentSessionId, setCurrentSessionId] = useState(urlSessionId || null)
  const [currentSession, setCurrentSession] = useState(null)
  const [activeTab, setActiveTab] = useState('papers')
  const [debouncedNoteChanges, setDebouncedNoteChanges] = useState({})

  const loadSessions = useCallback(async () => {
    try {
      const data = await api.getSessions()
      setSessions(data)
    } catch (error) {
      console.error('Error loading sessions:', error)
    }
  }, [])

  const loadSession = useCallback(async (id) => {
    try {
      const data = await api.getSession(id)
      setCurrentSession(data)
    } catch (error) {
      console.error('Error loading session:', error)
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

  const renderTabContent = () => {
    if (!currentSession) {
      return (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          height: '400px',
          color: '#64748b',
          fontStyle: 'italic'
        }}>
          Select a session from the sidebar to view details
        </div>
      )
    }

    switch (activeTab) {
      case 'papers':
        return (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            {currentSession.papers.map((paper) => (
              <PaperCard
                key={paper.id}
                paper={paper}
                showNotes={true}
                onNoteChange={handleNoteChange}
              />
            ))}
            {currentSession.papers.length === 0 && (
              <div style={{ color: '#64748b', fontStyle: 'italic', textAlign: 'center', padding: '2rem' }}>
                No papers in this session
              </div>
            )}
          </div>
        )
      case 'analysis':
        return <AnalysisCharts analysis={analysisMap} />
      case 'citations':
        return <CitationPanel papers={currentSession.papers} sessionId={currentSessionId} />
      case 'summary':
        return <SummaryPanel papers={currentSession.papers} sessionId={currentSessionId} onSynthesize={handleSynthesize} />
      default:
        return null
    }
  }

  return (
    <div style={{ display: 'flex', gap: '2rem', maxWidth: '1400px', margin: '0 auto' }}>
      <SessionSidebar
        sessions={sessions}
        currentSessionId={currentSessionId}
        onSelectSession={handleSelectSession}
      />

      <div style={{ flex: 1 }}>
        {currentSession && (
          <>
            <div style={{ marginBottom: '1.5rem' }}>
              <h2 style={{ color: '#f1f5f9', marginBottom: '0.5rem' }}>{currentSession.name}</h2>
              <p style={{ color: '#94a3b8', fontSize: '0.875rem' }}>
                Query: {currentSession.query}
              </p>
            </div>

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
                  {tab} {tab === 'papers' && currentSession.papers && `(${currentSession.papers.length})`}
                </button>
              ))}
            </div>

            {renderTabContent()}
          </>
        )}

        {!currentSession && (
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            height: '400px',
            background: '#1e293b',
            borderRadius: '12px',
            border: '1px solid #334155'
          }}>
            <div style={{ textAlign: 'center' }}>
              <div style={{ color: '#64748b', fontSize: '3rem', marginBottom: '1rem' }}>📚</div>
              <p style={{ color: '#94a3b8', fontSize: '1.1rem' }}>
                Select a session from the sidebar
              </p>
              <p style={{ color: '#64748b', marginTop: '0.5rem' }}>
                Or start a new search from the Search tab
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default Dashboard
