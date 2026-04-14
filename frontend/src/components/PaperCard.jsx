import React, { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Copy, Check, ExternalLink, BookOpen, X } from 'lucide-react'

function PaperCard({ paper, showNotes, onNoteChange, onCopyCitation }) {
  const [expanded, setExpanded] = useState(false)
  const [showCitationModal, setShowCitationModal] = useState(false)
  const [showSummary, setShowSummary] = useState(false)
  const [copiedFormat, setCopiedFormat] = useState(null)

  const formatAuthors = (authors) => {
    if (!authors || authors.length === 0) return 'Unknown'
    if (authors.length <= 3) return authors.join(', ')
    return `${authors.slice(0, 3).join(', ')} et al.`
  }

  const truncateAbstract = (text, maxLength = 180) => {
    if (!text) return null
    if (text.length <= maxLength) return text
    return text.slice(0, maxLength) + '...'
  }

  const handleCopyCitation = (format, text) => {
    navigator.clipboard.writeText(text)
    setCopiedFormat(format)
    setTimeout(() => setCopiedFormat(null), 2000)
    if (onCopyCitation) onCopyCitation(text)
  }

  return (
    <>
      <div className="card card-hover" style={{ padding: 'var(--space-5)' }}>
        {/* Header */}
        <div style={{ marginBottom: 'var(--space-4)' }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 'var(--space-4)', marginBottom: 'var(--space-2)' }}>
            <h3 className="paper-title" style={{ flex: 1 }}>{paper.title}</h3>
            {paper.relevance_score && (
              <span className="badge badge-primary" style={{ flexShrink: 0 }}>
                {(paper.relevance_score * 100).toFixed(0)}% match
              </span>
            )}
          </div>
          <div className="paper-authors" style={{ color: 'var(--text-secondary)', fontSize: 'var(--text-sm)' }}>
            {formatAuthors(paper.authors)} • {paper.year || 'N/A'} • {paper.source}
          </div>
        </div>

        {/* Citations Badge */}
        {(paper.citation_count !== null && paper.citation_count !== undefined) && (
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: 'var(--space-1)', marginBottom: 'var(--space-3)' }}>
            <BookOpen size={14} style={{ color: 'var(--text-tertiary)' }} />
            <span style={{ fontSize: 'var(--text-sm)', color: 'var(--text-secondary)' }}>
              {paper.citation_count.toLocaleString()} citations
            </span>
          </div>
        )}

        {/* Abstract */}
        {paper.abstract && (
          <p className="paper-abstract" style={{ marginBottom: 'var(--space-4)' }}>
            {expanded ? paper.abstract : truncateAbstract(paper.abstract)}
            {paper.abstract.length > 180 && (
              <button
                onClick={() => setExpanded(!expanded)}
                style={{ 
                  color: 'var(--accent-primary)', 
                  marginLeft: 'var(--space-2)',
                  fontSize: 'var(--text-sm)',
                  fontWeight: 'var(--font-medium)'
                }}
              >
                {expanded ? 'Show less' : 'Show more'}
              </button>
            )}
          </p>
        )}

        {/* Summary Panel */}
        <AnimatePresence>
          {showSummary && paper.summary && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              style={{ 
                background: 'var(--bg-secondary)', 
                borderRadius: 'var(--radius-lg)', 
                padding: 'var(--space-4)',
                marginBottom: 'var(--space-4)'
              }}
            >
              {paper.summary.abstract_compression && (
                <div style={{ marginBottom: 'var(--space-3)' }}>
                  <h4 style={{ fontSize: 'var(--text-sm)', fontWeight: 'var(--font-semibold)', marginBottom: 'var(--space-2)' }}>Summary</h4>
                  <p style={{ fontSize: 'var(--text-sm)', color: 'var(--text-secondary)', lineHeight: 'var(--leading-relaxed)' }}>
                    {paper.summary.abstract_compression}
                  </p>
                </div>
              )}
              {paper.summary.key_contributions && (
                <div style={{ marginBottom: 'var(--space-3)' }}>
                  <h4 style={{ fontSize: 'var(--text-sm)', fontWeight: 'var(--font-semibold)', marginBottom: 'var(--space-2)' }}>Key Contributions</h4>
                  <p style={{ fontSize: 'var(--text-sm)', color: 'var(--text-secondary)' }}>
                    {paper.summary.key_contributions}
                  </p>
                </div>
              )}
              {paper.summary.methodology && (
                <div>
                  <h4 style={{ fontSize: 'var(--text-sm)', fontWeight: 'var(--font-semibold)', marginBottom: 'var(--space-2)' }}>Methodology</h4>
                  <p style={{ fontSize: 'var(--text-sm)', color: 'var(--text-secondary)' }}>
                    {paper.summary.methodology}
                  </p>
                </div>
              )}
            </motion.div>
          )}
        </AnimatePresence>

        {/* Actions */}
        <div className="paper-footer" style={{ borderTop: '1px solid var(--card-border)', paddingTop: 'var(--space-4)', marginTop: 'auto' }}>
          <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
            <button
              className="btn btn-ghost btn-sm"
              onClick={() => setShowCitationModal(true)}
            >
              <Copy size={14} />
              Cite
            </button>
            <button
              className="btn btn-ghost btn-sm"
              onClick={() => setShowSummary(!showSummary)}
            >
              <BookOpen size={14} />
              {showSummary ? 'Hide' : 'Summary'}
            </button>
            {paper.source_url && (
              <a
                href={paper.source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="btn btn-ghost btn-sm"
              >
                <ExternalLink size={14} />
                Source
              </a>
            )}
          </div>
        </div>

        {/* Notes Section */}
        {showNotes && (
          <div style={{ marginTop: 'var(--space-4)', paddingTop: 'var(--space-4)', borderTop: '1px solid var(--card-border)' }}>
            <label style={{ fontSize: 'var(--text-xs)', fontWeight: 'var(--font-medium)', color: 'var(--text-tertiary)', display: 'block', marginBottom: 'var(--space-2)' }}>
              Notes
            </label>
            <textarea
              className="form-input"
              placeholder="Add notes..."
              defaultValue={paper.notes?.[0]?.content || ''}
              onBlur={(e) => onNoteChange && onNoteChange(paper.id, e.target.value)}
              style={{ 
                minHeight: '80px', 
                resize: 'vertical',
                fontSize: 'var(--text-sm)',
                background: 'var(--bg-secondary)'
              }}
            />
          </div>
        )}
      </div>

      {/* Citation Modal */}
      <AnimatePresence>
        {showCitationModal && paper.citation && (
          <motion.div
            className="modal-backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setShowCitationModal(false)}
          >
            <motion.div
              className="modal"
              initial={{ opacity: 0, scale: 0.95, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 20 }}
              onClick={(e) => e.stopPropagation()}
            >
              <div className="modal-header">
                <h3 className="modal-title">Cite this paper</h3>
                <button className="btn btn-ghost btn-icon" onClick={() => setShowCitationModal(false)}>
                  <X size={18} />
                </button>
              </div>
              <div className="modal-body" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
                {['apa', 'mla', 'ieee', 'chicago'].map((style) => (
                  <div key={style} style={{ padding: 'var(--space-3)', background: 'var(--bg-secondary)', borderRadius: 'var(--radius-md)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-2)' }}>
                      <span style={{ fontSize: 'var(--text-xs)', fontWeight: 'var(--font-semibold)', textTransform: 'uppercase', color: 'var(--text-tertiary)' }}>
                        {style}
                      </span>
                      <button
                        className="btn btn-ghost btn-sm"
                        onClick={() => handleCopyCitation(style, paper.citation[style])}
                      >
                        {copiedFormat === style ? (
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
                    <p style={{ fontSize: 'var(--text-sm)', color: 'var(--text-secondary)', lineHeight: 'var(--leading-relaxed)' }}>
                      {paper.citation[style] || 'Not available'}
                    </p>
                  </div>
                ))}
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  )
}

export default PaperCard
