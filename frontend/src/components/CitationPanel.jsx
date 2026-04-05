import React, { useState } from 'react'

function CitationPanel({ papers, sessionId }) {
  const [selectedPapers, setSelectedPapers] = useState([])
  const [selectedStyle, setSelectedStyle] = useState({})
  const [copiedId, setCopiedId] = useState(null)

  const togglePaper = (paperId) => {
    setSelectedPapers(prev =>
      prev.includes(paperId)
        ? prev.filter(id => id !== paperId)
        : [...prev, paperId]
    )
  }

  const copyToClipboard = (text, paperId) => {
    navigator.clipboard.writeText(text)
    setCopiedId(paperId)
    setTimeout(() => setCopiedId(null), 2000)
  }

  const handleExport = (format) => {
    const baseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
    window.open(`${baseUrl}/sessions/${sessionId}/export/${format}`, '_blank')
  }

  return (
    <div>
      {selectedPapers.length > 0 && (
        <div style={{
          background: '#1e293b',
          padding: '1rem',
          borderRadius: '8px',
          marginBottom: '1rem',
          display: 'flex',
          alignItems: 'center',
          gap: '1rem',
          flexWrap: 'wrap'
        }}>
          <span style={{ color: '#e2e8f0' }}>
            {selectedPapers.length} paper{selectedPapers.length > 1 ? 's' : ''} selected
          </span>
          <button
            onClick={() => handleExport('bib')}
            style={{
              background: '#60a5fa',
              color: '#0f172a',
              border: 'none',
              padding: '0.5rem 1rem',
              borderRadius: '6px',
              cursor: 'pointer',
              fontWeight: '600'
            }}
          >
            Export .bib
          </button>
          <button
            onClick={() => handleExport('txt')}
            style={{
              background: '#a78bfa',
              color: '#0f172a',
              border: 'none',
              padding: '0.5rem 1rem',
              borderRadius: '6px',
              cursor: 'pointer',
              fontWeight: '600'
            }}
          >
            Export .txt
          </button>
        </div>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        {papers.map((paper) => (
          <div
            key={paper.id}
            style={{
              background: '#1e293b',
              padding: '1.5rem',
              borderRadius: '12px',
              border: '1px solid #334155'
            }}
          >
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: '1rem', marginBottom: '1rem' }}>
              <input
                type="checkbox"
                checked={selectedPapers.includes(paper.id)}
                onChange={() => togglePaper(paper.id)}
                style={{ marginTop: '0.25rem', width: '18px', height: '18px', cursor: 'pointer' }}
              />
              <div style={{ flex: 1 }}>
                <h4 style={{ color: '#f1f5f9', marginBottom: '0.25rem' }}>{paper.title}</h4>
                <p style={{ color: '#94a3b8', fontSize: '0.875rem' }}>
                  {paper.authors?.slice(0, 3).join(', ')}
                  {paper.authors?.length > 3 && ' et al.'}
                  {' • '}{paper.year}
                </p>
              </div>
            </div>

            {paper.citation && (
              <div style={{ marginTop: '1rem' }}>
                <select
                  value={selectedStyle[paper.id] || 'apa'}
                  onChange={(e) => setSelectedStyle({ ...selectedStyle, [paper.id]: e.target.value })}
                  style={{
                    background: '#0f172a',
                    color: '#e2e8f0',
                    border: '1px solid #334155',
                    padding: '0.5rem 1rem',
                    borderRadius: '6px',
                    marginBottom: '0.75rem',
                    cursor: 'pointer'
                  }}
                >
                  <option value="apa">APA</option>
                  <option value="mla">MLA</option>
                  <option value="ieee">IEEE</option>
                  <option value="chicago">Chicago</option>
                </select>

                <div style={{
                  background: '#0f172a',
                  padding: '1rem',
                  borderRadius: '8px',
                  position: 'relative'
                }}>
                  <p style={{
                    color: '#cbd5e1',
                    fontSize: '0.875rem',
                    lineHeight: '1.6',
                    paddingRight: '3rem'
                  }}>
                    {paper.citation[selectedStyle[paper.id] || 'apa'] || 'Citation not available'}
                  </p>
                  <button
                    onClick={() => copyToClipboard(
                      paper.citation[selectedStyle[paper.id] || 'apa'] || '',
                      paper.id
                    )}
                    style={{
                      position: 'absolute',
                      top: '0.75rem',
                      right: '0.75rem',
                      background: '#334155',
                      color: copiedId === paper.id ? '#22c55e' : '#e2e8f0',
                      border: 'none',
                      padding: '0.25rem 0.5rem',
                      borderRadius: '4px',
                      cursor: 'pointer',
                      fontSize: '0.75rem'
                    }}
                  >
                    {copiedId === paper.id ? 'Copied!' : 'Copy'}
                  </button>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>

      {papers.length === 0 && (
        <div style={{ color: '#64748b', fontStyle: 'italic', textAlign: 'center', padding: '2rem' }}>
          No papers available
        </div>
      )}
    </div>
  )
}

export default CitationPanel
