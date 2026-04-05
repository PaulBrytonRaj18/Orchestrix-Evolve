import React, { useState } from 'react'

function PaperCard({ paper, showNotes, onNoteChange, onCopyCitation, onViewCitations }) {
  const [expanded, setExpanded] = useState(false)
  const [showCitationModal, setShowCitationModal] = useState(false)
  const [showSummary, setShowSummary] = useState(false)

  const getScoreColor = (score) => {
    if (score >= 0.7) return '#22c55e'
    if (score >= 0.4) return '#eab308'
    return '#64748b'
  }

  const formatAuthors = (authors) => {
    if (!authors || authors.length === 0) return 'Unknown'
    if (authors.length <= 3) return authors.join(', ')
    return `${authors.slice(0, 3).join(', ')} et al.`
  }

  const truncateAbstract = (text, maxLength = 200) => {
    if (!text) return 'No abstract available.'
    if (text.length <= maxLength) return text
    return text.slice(0, maxLength) + '...'
  }

  return (
    <div style={{
      background: '#1e293b',
      borderRadius: '12px',
      padding: '1.5rem',
      border: '1px solid #334155'
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.75rem' }}>
        <h3 style={{ fontSize: '1.1rem', color: '#f1f5f9', flex: 1, marginRight: '1rem' }}>
          {paper.title}
        </h3>
        {paper.relevance_score && (
          <span style={{
            background: getScoreColor(paper.relevance_score),
            color: '#0f172a',
            padding: '0.25rem 0.5rem',
            borderRadius: '4px',
            fontSize: '0.75rem',
            fontWeight: 'bold',
            whiteSpace: 'nowrap'
          }}>
            Score: {paper.relevance_score.toFixed(2)}
          </span>
        )}
      </div>

      <div style={{ fontSize: '0.875rem', color: '#94a3b8', marginBottom: '0.5rem' }}>
        {formatAuthors(paper.authors)} • {paper.year || 'Unknown year'} • {paper.source}
      </div>

      {paper.citation_count !== null && paper.citation_count !== undefined && (
        <div style={{ fontSize: '0.875rem', color: '#60a5fa', marginBottom: '0.75rem' }}>
          Citations: {paper.citation_count}
        </div>
      )}

      <p style={{ fontSize: '0.875rem', color: '#cbd5e1', lineHeight: '1.6', marginBottom: '1rem' }}>
        {expanded ? paper.abstract : truncateAbstract(paper.abstract)}
        {paper.abstract && paper.abstract.length > 200 && (
          <button
            onClick={() => setExpanded(!expanded)}
            style={{
              background: 'none',
              border: 'none',
              color: '#60a5fa',
              cursor: 'pointer',
              marginLeft: '0.5rem',
              fontSize: '0.875rem'
            }}
          >
            {expanded ? 'Show less' : 'Show more'}
          </button>
        )}
      </p>

      <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
        {paper.citation && paper.citation.apa && (
          <button
            onClick={() => onCopyCitation && onCopyCitation(paper.citation.apa)}
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
            Copy APA
          </button>
        )}
        <button
          onClick={() => setShowCitationModal(true)}
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
          All Citations
        </button>
        <button
          onClick={() => setShowSummary(!showSummary)}
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
          {showSummary ? 'Hide Summary' : 'View Summary'}
        </button>
      </div>

      {showSummary && paper.summary && (
        <div style={{
          marginTop: '1rem',
          padding: '1rem',
          background: '#0f172a',
          borderRadius: '8px',
          border: '1px solid #334155'
        }}>
          <div style={{ marginBottom: '1rem' }}>
            <div style={{ fontWeight: '600', color: '#60a5fa', marginBottom: '0.5rem' }}>
              Summary
            </div>
            <p style={{ fontSize: '0.875rem', color: '#cbd5e1' }}>
              {paper.summary.abstract_compression || 'No summary available.'}
            </p>
          </div>
          {paper.summary.key_contributions && (
            <div style={{ marginBottom: '1rem' }}>
              <div style={{ fontWeight: '600', color: '#60a5fa', marginBottom: '0.5rem' }}>
                Key Contributions
              </div>
              <p style={{ fontSize: '0.875rem', color: '#cbd5e1', whiteSpace: 'pre-wrap' }}>
                {paper.summary.key_contributions}
              </p>
            </div>
          )}
          {paper.summary.methodology && (
            <div style={{ marginBottom: '1rem' }}>
              <div style={{ fontWeight: '600', color: '#60a5fa', marginBottom: '0.5rem' }}>
                Methodology
              </div>
              <p style={{ fontSize: '0.875rem', color: '#cbd5e1' }}>
                {paper.summary.methodology}
              </p>
            </div>
          )}
          {paper.summary.limitations && (
            <div>
              <div style={{ fontWeight: '600', color: '#60a5fa', marginBottom: '0.5rem' }}>
                Limitations
              </div>
              <p style={{ fontSize: '0.875rem', color: '#cbd5e1' }}>
                {paper.summary.limitations}
              </p>
            </div>
          )}
        </div>
      )}

      {showNotes && (
        <div style={{ marginTop: '1rem' }}>
          <textarea
            placeholder="Add notes..."
            defaultValue={paper.notes?.[0]?.content || ''}
            onBlur={(e) => onNoteChange && onNoteChange(paper.id, e.target.value)}
            style={{
              width: '100%',
              minHeight: '80px',
              padding: '0.75rem',
              background: '#0f172a',
              border: '1px solid #334155',
              borderRadius: '8px',
              color: '#e2e8f0',
              fontSize: '0.875rem',
              resize: 'vertical'
            }}
          />
        </div>
      )}

      {showCitationModal && paper.citation && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'rgba(0,0,0,0.8)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000
          }}
          onClick={() => setShowCitationModal(false)}
        >
          <div
            style={{
              background: '#1e293b',
              padding: '2rem',
              borderRadius: '12px',
              maxWidth: '600px',
              width: '90%',
              maxHeight: '80vh',
              overflow: 'auto'
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <h3 style={{ marginBottom: '1.5rem', color: '#f1f5f9' }}>Citation Formats</h3>
            {['apa', 'mla', 'ieee', 'chicago'].map((style) => (
              <div key={style} style={{ marginBottom: '1rem' }}>
                <div style={{ fontWeight: '600', color: '#60a5fa', marginBottom: '0.25rem' }}>
                  {style.toUpperCase()}
                </div>
                <p style={{ fontSize: '0.875rem', color: '#cbd5e1', lineHeight: '1.6' }}>
                  {paper.citation[style] || 'Not available'}
                </p>
              </div>
            ))}
            <button
              onClick={() => setShowCitationModal(false)}
              style={{
                marginTop: '1rem',
                background: '#334155',
                color: '#e2e8f0',
                border: 'none',
                padding: '0.75rem 1.5rem',
                borderRadius: '6px',
                cursor: 'pointer'
              }}
            >
              Close
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

export default PaperCard
