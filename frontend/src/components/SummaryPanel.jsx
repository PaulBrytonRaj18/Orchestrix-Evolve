import React, { useState } from 'react'

function SummaryPanel({ papers, sessionId, onSynthesize }) {
  const [expandedPapers, setExpandedPapers] = useState({})
  const [selectedForSynthesis, setSelectedForSynthesis] = useState([])

  const toggleExpand = (paperId) => {
    setExpandedPapers(prev => ({
      ...prev,
      [paperId]: !prev[paperId]
    }))
  }

  const toggleForSynthesis = (paperId) => {
    setSelectedForSynthesis(prev =>
      prev.includes(paperId)
        ? prev.filter(id => id !== paperId)
        : [...prev, paperId]
    )
  }

  return (
    <div>
      <div style={{
        background: '#1e293b',
        padding: '1rem',
        borderRadius: '8px',
        marginBottom: '1.5rem',
        display: 'flex',
        alignItems: 'center',
        gap: '1rem',
        flexWrap: 'wrap'
      }}>
        <span style={{ color: '#e2e8f0' }}>
          {selectedForSynthesis.length} paper{selectedForSynthesis.length !== 1 ? 's' : ''} selected for synthesis
        </span>
        <button
          onClick={() => onSynthesize && onSynthesize(selectedForSynthesis)}
          disabled={selectedForSynthesis.length < 2}
          style={{
            background: selectedForSynthesis.length >= 2 ? '#60a5fa' : '#334155',
            color: selectedForSynthesis.length >= 2 ? '#0f172a' : '#64748b',
            border: 'none',
            padding: '0.5rem 1rem',
            borderRadius: '6px',
            cursor: selectedForSynthesis.length >= 2 ? 'pointer' : 'not-allowed',
            fontWeight: '600'
          }}
        >
          Synthesize Selected Papers
        </button>
      </div>

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
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: '1rem' }}>
              <input
                type="checkbox"
                checked={selectedForSynthesis.includes(paper.id)}
                onChange={() => toggleForSynthesis(paper.id)}
                style={{ marginTop: '0.25rem', width: '18px', height: '18px', cursor: 'pointer' }}
              />
              <div style={{ flex: 1 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <h4 style={{ color: '#f1f5f9', marginBottom: '0.5rem' }}>{paper.title}</h4>
                  <button
                    onClick={() => toggleExpand(paper.id)}
                    style={{
                      background: '#334155',
                      color: '#e2e8f0',
                      border: 'none',
                      padding: '0.5rem 1rem',
                      borderRadius: '6px',
                      cursor: 'pointer',
                      fontSize: '0.875rem'
                    }}
                  >
                    {expandedPapers[paper.id] ? 'Collapse' : 'Expand'}
                  </button>
                </div>
                <p style={{ color: '#94a3b8', fontSize: '0.875rem' }}>
                  {paper.authors?.slice(0, 3).join(', ')}
                  {paper.authors?.length > 3 && ' et al.'}
                  {' • '}{paper.year}
                </p>
              </div>
            </div>

            {paper.summary ? (
              <>
                <div style={{ marginTop: '1rem' }}>
                  <h5 style={{ color: '#60a5fa', marginBottom: '0.5rem', fontSize: '0.875rem' }}>
                    Summary
                  </h5>
                  <p style={{ color: '#cbd5e1', fontSize: '0.875rem', lineHeight: '1.6' }}>
                    {paper.summary.abstract_compression || 'No summary available.'}
                  </p>
                </div>

                {expandedPapers[paper.id] && (
                  <>
                    {paper.summary.key_contributions && (
                      <div style={{ marginTop: '1rem' }}>
                        <h5 style={{ color: '#60a5fa', marginBottom: '0.5rem', fontSize: '0.875rem' }}>
                          Key Contributions
                        </h5>
                        <p style={{ color: '#cbd5e1', fontSize: '0.875rem', lineHeight: '1.6', whiteSpace: 'pre-wrap' }}>
                          {paper.summary.key_contributions}
                        </p>
                      </div>
                    )}

                    {paper.summary.methodology && (
                      <div style={{ marginTop: '1rem' }}>
                        <h5 style={{ color: '#60a5fa', marginBottom: '0.5rem', fontSize: '0.875rem' }}>
                          Methodology
                        </h5>
                        <p style={{ color: '#cbd5e1', fontSize: '0.875rem', lineHeight: '1.6' }}>
                          {paper.summary.methodology}
                        </p>
                      </div>
                    )}

                    {paper.summary.limitations && (
                      <div style={{ marginTop: '1rem' }}>
                        <h5 style={{ color: '#60a5fa', marginBottom: '0.5rem', fontSize: '0.875rem' }}>
                          Limitations
                        </h5>
                        <p style={{ color: '#cbd5e1', fontSize: '0.875rem', lineHeight: '1.6' }}>
                          {paper.summary.limitations}
                        </p>
                      </div>
                    )}
                  </>
                )}
              </>
            ) : (
              <div style={{ marginTop: '1rem', color: '#64748b', fontStyle: 'italic' }}>
                Summary not available
              </div>
            )}
          </div>
        ))}
      </div>

      {papers.length === 0 && (
        <div style={{ color: '#64748b', fontStyle: 'italic', textAlign: 'center', padding: '2rem' }}>
          No papers with summaries available
        </div>
      )}
    </div>
  )
}

export default SummaryPanel
