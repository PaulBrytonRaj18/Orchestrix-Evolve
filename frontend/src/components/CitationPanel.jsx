import React, { useState } from 'react'
import { motion } from 'framer-motion'
import { Copy, Check, Link2 } from 'lucide-react'

function CitationPanel({ papers, sessionId }) {
  const [selectedStyle, setSelectedStyle] = useState('apa')
  const [copiedId, setCopiedId] = useState(null)

  const citationStyles = ['apa', 'mla', 'ieee', 'chicago']

  const copyToClipboard = (text, paperId) => {
    navigator.clipboard.writeText(text)
    setCopiedId(paperId)
    setTimeout(() => setCopiedId(null), 2000)
  }

  if (!papers || papers.length === 0) {
    return (
      <div className="empty-state">
        <div className="empty-icon">
          <Link2 size={32} strokeWidth={1} />
        </div>
        <h3 className="empty-title">No papers to cite</h3>
        <p className="empty-description">
          Add papers to your session to generate citations
        </p>
      </div>
    )
  }

  return (
    <div>
      {/* Style Selector */}
      <div style={{ display: 'flex', gap: 'var(--space-2)', marginBottom: 'var(--space-6)' }}>
        {citationStyles.map((style) => (
          <button
            key={style}
            onClick={() => setSelectedStyle(style)}
            className={`btn ${selectedStyle === style ? 'btn-primary' : 'btn-secondary'}`}
            style={{ textTransform: 'uppercase', fontSize: 'var(--text-xs)', fontWeight: 'var(--font-semibold)' }}
          >
            {style}
          </button>
        ))}
      </div>

      {/* Citations List */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
        {papers.map((paper) => (
          <motion.div
            key={paper.id}
            className="card"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            style={{ padding: 'var(--space-5)' }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 'var(--space-3)' }}>
              <div style={{ flex: 1, minWidth: 0 }}>
                <h4 style={{ fontSize: 'var(--text-sm)', fontWeight: 'var(--font-semibold)', marginBottom: 'var(--space-1)', lineHeight: 'var(--leading-tight)' }}>
                  {paper.title}
                </h4>
                <p style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>
                  {paper.authors?.slice(0, 3).join(', ')}
                  {paper.authors?.length > 3 && ' et al.'}
                  {paper.year && ` • ${paper.year}`}
                </p>
              </div>
              <button
                className="btn btn-ghost btn-sm"
                onClick={() => copyToClipboard(paper.citation?.[selectedStyle] || '', paper.id)}
                style={{ flexShrink: 0 }}
              >
                {copiedId === paper.id ? (
                  <>
                    <Check size={14} style={{ color: 'var(--success-primary)' }} />
                    Copied
                  </>
                ) : (
                  <>
                    <Copy size={14} />
                    Copy
                  </>
                )}
              </button>
            </div>
            {paper.citation?.[selectedStyle] ? (
              <p style={{ 
                fontSize: 'var(--text-sm)', 
                color: 'var(--text-secondary)', 
                lineHeight: 'var(--leading-relaxed)',
                padding: 'var(--space-3)',
                background: 'var(--bg-secondary)',
                borderRadius: 'var(--radius-md)'
              }}>
                {paper.citation[selectedStyle]}
              </p>
            ) : (
              <p style={{ fontSize: 'var(--text-sm)', color: 'var(--text-tertiary)', fontStyle: 'italic' }}>
                Citation not available in {selectedStyle.toUpperCase()} format
              </p>
            )}
          </motion.div>
        ))}
      </div>
    </div>
  )
}

export default CitationPanel
