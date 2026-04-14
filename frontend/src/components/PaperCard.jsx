import React, { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import '../component.css'

function PaperCard({ paper, showNotes, onNoteChange, onCopyCitation, onViewCitations }) {
  const [expanded, setExpanded] = useState(false)
  const [showCitationModal, setShowCitationModal] = useState(false)
  const [showSummary, setShowSummary] = useState(false)
  const [copiedFormat, setCopiedFormat] = useState(null)

  const getScoreColor = (score) => {
    if (score >= 0.7) return 'high'
    if (score >= 0.4) return 'medium'
    return 'low'
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

  const handleCopyCitation = (format, text) => {
    navigator.clipboard.writeText(text)
    setCopiedFormat(format)
    setTimeout(() => setCopiedFormat(null), 2000)
    if (onCopyCitation) onCopyCitation(text)
  }

  return (
    <motion.div 
      className="paper-card"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ scale: 1.01 }}
      transition={{ type: "spring", stiffness: 300, damping: 20 }}
    >
      <div className="paper-card-glow" />
      
      {/* Header */}
      <div className="paper-card-header">
        <div className="paper-title-section">
          <h3 className="paper-title">{paper.title}</h3>
          <div className="paper-meta">
            <span className="paper-authors">{formatAuthors(paper.authors)}</span>
            <span className="meta-separator">•</span>
            <span className="paper-year">{paper.year || 'Unknown year'}</span>
            <span className="meta-separator">•</span>
            <span className="paper-source">{paper.source}</span>
          </div>
        </div>
        
        {paper.relevance_score && (
          <motion.div 
            className={`relevance-badge ${getScoreColor(paper.relevance_score)}`}
            whileHover={{ scale: 1.1 }}
            whileTap={{ scale: 0.95 }}
          >
            <span className="score-icon">⚡</span>
            <span className="score-value">{(paper.relevance_score * 100).toFixed(0)}%</span>
          </motion.div>
        )}
      </div>

      {/* Citation Count */}
      <div 
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '8px',
          padding: '8px 16px',
          background: 'linear-gradient(135deg, rgba(220, 38, 38, 0.2) 0%, rgba(127, 29, 29, 0.25) 100%)',
          border: '1px solid rgba(220, 38, 38, 0.4)',
          borderRadius: '20px',
          marginBottom: '12px',
          fontSize: '14px',
        }}
      >
        <span style={{ fontSize: '16px' }}>📚</span>
        <span style={{ color: '#dc2626', fontWeight: 'bold', fontSize: '16px' }}>
          {(paper.citation_count !== null && paper.citation_count !== undefined && paper.citation_count > 0) 
            ? paper.citation_count.toLocaleString() 
            : '0'}
        </span>
        <span style={{ color: '#a1a1aa', fontSize: '13px' }}>citations</span>
      </div>

      {/* Abstract */}
      <div className="paper-abstract">
        <p>
          {expanded ? paper.abstract : truncateAbstract(paper.abstract)}
          {paper.abstract && paper.abstract.length > 200 && (
            <motion.button
              className="expand-button"
              onClick={() => setExpanded(!expanded)}
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
            >
              {expanded ? '← Show less' : 'Show more →'}
            </motion.button>
          )}
        </p>
      </div>

      {/* Action Buttons */}
      <div className="paper-actions">
        {paper.citation && paper.citation.apa && (
          <motion.button
            className="action-button primary"
            onClick={() => handleCopyCitation('apa', paper.citation.apa)}
            whileHover={{ scale: 1.05, y: -2 }}
            whileTap={{ scale: 0.95 }}
          >
            <span className="button-icon">📋</span>
            <span>Copy APA</span>
          </motion.button>
        )}
        
        <motion.button
          className="action-button secondary"
          onClick={() => setShowCitationModal(true)}
          whileHover={{ scale: 1.05, y: -2 }}
          whileTap={{ scale: 0.95 }}
        >
          <span className="button-icon">🔗</span>
          <span>All Citations</span>
        </motion.button>
        
        <motion.button
          className={`action-button ${showSummary ? 'active' : 'secondary'}`}
          onClick={() => setShowSummary(!showSummary)}
          whileHover={{ scale: 1.05, y: -2 }}
          whileTap={{ scale: 0.95 }}
        >
          <span className="button-icon">{showSummary ? '✨' : '📝'}</span>
          <span>{showSummary ? 'Hide Summary' : 'View Summary'}</span>
        </motion.button>
      </div>

      {/* Summary Panel */}
      <AnimatePresence>
        {showSummary && paper.summary && (
          <motion.div
            className="summary-panel"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.3, ease: "easeInOut" }}
          >
            <div className="summary-glow" />
            
            <div className="summary-section">
              <div className="summary-header">
                <span className="summary-icon">📄</span>
                <span className="summary-title">Summary</span>
              </div>
              <p className="summary-content">
                {paper.summary.abstract_compression || 'No summary available.'}
              </p>
            </div>

            {paper.summary.key_contributions && (
              <div className="summary-section">
                <div className="summary-header">
                  <span className="summary-icon">🎯</span>
                  <span className="summary-title">Key Contributions</span>
                </div>
                <p className="summary-content">{paper.summary.key_contributions}</p>
              </div>
            )}

            {paper.summary.methodology && (
              <div className="summary-section">
                <div className="summary-header">
                  <span className="summary-icon">🔬</span>
                  <span className="summary-title">Methodology</span>
                </div>
                <p className="summary-content">{paper.summary.methodology}</p>
              </div>
            )}

            {paper.summary.limitations && (
              <div className="summary-section">
                <div className="summary-header">
                  <span className="summary-icon">⚠️</span>
                  <span className="summary-title">Limitations</span>
                </div>
                <p className="summary-content">{paper.summary.limitations}</p>
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Notes Section */}
      {showNotes && (
        <motion.div 
          className="notes-section"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.2 }}
        >
          <div className="notes-header">
            <span className="notes-icon">✏️</span>
            <span className="notes-title">Notes</span>
          </div>
          <textarea
            className="notes-textarea"
            placeholder="Add your notes here..."
            defaultValue={paper.notes?.[0]?.content || ''}
            onBlur={(e) => onNoteChange && onNoteChange(paper.id, e.target.value)}
          />
        </motion.div>
      )}

      {/* Citation Modal */}
      <AnimatePresence>
        {showCitationModal && paper.citation && (
          <motion.div
            className="modal-overlay"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setShowCitationModal(false)}
          >
            <motion.div
              className="citation-modal"
              initial={{ opacity: 0, scale: 0.9, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.9, y: 20 }}
              transition={{ type: "spring", stiffness: 300, damping: 25 }}
              onClick={(e) => e.stopPropagation()}
            >
              <div className="modal-glow" />
              
              <div className="modal-header">
                <h3 className="modal-title">
                  <span className="modal-icon">📚</span>
                  Citation Formats
                </h3>
                <motion.button
                  className="modal-close"
                  onClick={() => setShowCitationModal(false)}
                  whileHover={{ scale: 1.1, rotate: 90 }}
                  whileTap={{ scale: 0.9 }}
                >
                  ✕
                </motion.button>
              </div>

              <div className="citation-formats">
                {['apa', 'mla', 'ieee', 'chicago'].map((style, index) => (
                  <motion.div 
                    key={style} 
                    className="citation-format"
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: index * 0.1 }}
                  >
                    <div className="format-header">
                      <span className="format-name">{style.toUpperCase()}</span>
                      <motion.button
                        className={`copy-button ${copiedFormat === style ? 'copied' : ''}`}
                        onClick={() => handleCopyCitation(style, paper.citation[style])}
                        whileHover={{ scale: 1.05 }}
                        whileTap={{ scale: 0.95 }}
                      >
                        {copiedFormat === style ? '✓ Copied!' : '📋 Copy'}
                      </motion.button>
                    </div>
                    <p className="format-text">
                      {paper.citation[style] || 'Not available'}
                    </p>
                  </motion.div>
                ))}
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}

export default PaperCard
