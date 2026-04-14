import React, { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import '../component.css'

const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.08,
      delayChildren: 0.1
    }
  }
}

const itemVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: {
    opacity: 1,
    y: 0,
    transition: {
      type: "spring",
      stiffness: 100,
      damping: 12
    }
  }
}

const pulseVariants = {
  pulse: {
    scale: [1, 1.02, 1],
    opacity: [0.6, 1, 0.6],
    transition: {
      duration: 2,
      repeat: Infinity,
      ease: "easeInOut"
    }
  }
}

function CitationPanel({ papers, sessionId }) {
  const [selectedPapers, setSelectedPapers] = useState([])
  const [selectedStyle, setSelectedStyle] = useState({})
  const [copiedId, setCopiedId] = useState(null)
  const [isExporting, setIsExporting] = useState(false)

  const togglePaper = (paperId) => {
    setSelectedPapers(prev =>
      prev.includes(paperId)
        ? prev.filter(id => id !== paperId)
        : [...prev, paperId]
    )
  }

  const selectAll = () => {
    if (selectedPapers.length === papers.length) {
      setSelectedPapers([])
    } else {
      setSelectedPapers(papers.map(p => p.id))
    }
  }

  const copyToClipboard = (text, paperId) => {
    navigator.clipboard.writeText(text)
    setCopiedId(paperId)
    setTimeout(() => setCopiedId(null), 2000)
  }

  const copyAllSelected = () => {
    const selectedCitations = papers
      .filter(p => selectedPapers.includes(p.id))
      .map(p => p.citation?.[selectedStyle[p.id] || 'apa'] || '')
      .filter(c => c)
      .join('\n\n')
    
    if (selectedCitations) {
      navigator.clipboard.writeText(selectedCitations)
      setCopiedId('all')
      setTimeout(() => setCopiedId(null), 2000)
    }
  }

  const handleExport = async (format) => {
    setIsExporting(true)
    try {
      const baseUrl = import.meta.env.VITE_API_BASE_URL || '[localhost](http://localhost:8000)'
      window.open(`${baseUrl}/sessions/${sessionId}/export/${format}`, '_blank')
    } finally {
      setTimeout(() => setIsExporting(false), 1000)
    }
  }

  const citationStyles = [
    { id: 'apa', label: 'APA', icon: '📘' },
    { id: 'mla', label: 'MLA', icon: '📗' },
    { id: 'ieee', label: 'IEEE', icon: '📙' },
    { id: 'chicago', label: 'Chicago', icon: '📕' }
  ]

  return (
    <div className="citation-panel">
      {/* Header Actions Bar */}
      <AnimatePresence>
        {selectedPapers.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: -20, height: 0 }}
            animate={{ opacity: 1, y: 0, height: 'auto' }}
            exit={{ opacity: 0, y: -20, height: 0 }}
            className="citation-actions-bar"
          >
            <motion.div 
              className="actions-glow"
              variants={pulseVariants}
              animate="pulse"
            />
            <div className="actions-content">
              <div className="selection-info">
                <motion.div 
                  className="selection-badge"
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                  transition={{ type: "spring", stiffness: 500 }}
                >
                  <span className="selection-count">{selectedPapers.length}</span>
                </motion.div>
                <span className="selection-text">
                  paper{selectedPapers.length > 1 ? 's' : ''} selected
                </span>
              </div>
              
              <div className="action-buttons">
                <motion.button
                  whileHover={{ scale: 1.05, y: -2 }}
                  whileTap={{ scale: 0.95 }}
                  onClick={copyAllSelected}
                  className="action-btn copy-btn"
                >
                  <span className="btn-icon">{copiedId === 'all' ? '✓' : '📋'}</span>
                  <span className="btn-label">{copiedId === 'all' ? 'Copied!' : 'Copy All'}</span>
                </motion.button>
                
                <motion.button
                  whileHover={{ scale: 1.05, y: -2 }}
                  whileTap={{ scale: 0.95 }}
                  onClick={() => handleExport('bib')}
                  className="action-btn export-bib-btn"
                  disabled={isExporting}
                >
                  <span className="btn-icon">📄</span>
                  <span className="btn-label">.bib</span>
                </motion.button>
                
                <motion.button
                  whileHover={{ scale: 1.05, y: -2 }}
                  whileTap={{ scale: 0.95 }}
                  onClick={() => handleExport('txt')}
                  className="action-btn export-txt-btn"
                  disabled={isExporting}
                >
                  <span className="btn-icon">📝</span>
                  <span className="btn-label">.txt</span>
                </motion.button>
                
                <motion.button
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                  onClick={() => setSelectedPapers([])}
                  className="action-btn clear-btn"
                >
                  <span className="btn-icon">✕</span>
                </motion.button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Select All Toggle */}
      {papers.length > 0 && (
        <motion.div 
          className="select-all-bar"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.2 }}
        >
          <label className="select-all-label">
            <input
              type="checkbox"
              checked={selectedPapers.length === papers.length && papers.length > 0}
              onChange={selectAll}
              className="select-all-checkbox"
            />
            <span className="checkbox-custom"></span>
            <span className="select-all-text">
              {selectedPapers.length === papers.length ? 'Deselect All' : 'Select All'}
            </span>
          </label>
          <span className="total-count">{papers.length} papers</span>
        </motion.div>
      )}

      {/* Citations List */}
      <motion.div
        variants={containerVariants}
        initial="hidden"
        animate="visible"
        className="citations-list"
      >
        {papers.map((paper, index) => (
          <motion.div
            key={paper.id}
            variants={itemVariants}
            className={`citation-card ${selectedPapers.includes(paper.id) ? 'selected' : ''}`}
            whileHover={{ 
              scale: 1.01,
              y: -4,
              transition: { type: "spring", stiffness: 300 }
            }}
          >
            <div className="card-glow"></div>
            
            {/* Card Header */}
            <div className="citation-card-header">
              <label className="paper-checkbox-label">
                <input
                  type="checkbox"
                  checked={selectedPapers.includes(paper.id)}
                  onChange={() => togglePaper(paper.id)}
                  className="paper-checkbox"
                />
                <motion.span 
                  className="checkbox-custom"
                  animate={selectedPapers.includes(paper.id) ? {
                    scale: [1, 1.2, 1],
                    transition: { duration: 0.3 }
                  } : {}}
                >
                  {selectedPapers.includes(paper.id) && (
                    <motion.span
                      initial={{ scale: 0 }}
                      animate={{ scale: 1 }}
                      className="check-icon"
                    >
                      ✓
                    </motion.span>
                  )}
                </motion.span>
              </label>
              
              <div className="paper-info">
                <h4 className="paper-title">{paper.title}</h4>
                <p className="paper-authors">
                  {paper.authors?.slice(0, 3).join(', ')}
                  {paper.authors?.length > 3 && <span className="et-al"> et al.</span>}
                  <span className="paper-year"> • {paper.year}</span>
                </p>
              </div>
              
              <div className="paper-badges">
                {paper.doi && (
                  <span className="badge doi-badge">DOI</span>
                )}
                {paper.citation && (
                  <span className="badge citation-badge">Cited</span>
                )}
              </div>
            </div>

            {/* Citation Styles */}
            {paper.citation && (
              <motion.div 
                className="citation-content"
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                transition={{ delay: 0.1 }}
              >
                <div className="style-selector">
                  {citationStyles.map((style) => (
                    <motion.button
                      key={style.id}
                      whileHover={{ scale: 1.05 }}
                      whileTap={{ scale: 0.95 }}
                      onClick={() => setSelectedStyle({ ...selectedStyle, [paper.id]: style.id })}
                      className={`style-btn ${(selectedStyle[paper.id] || 'apa') === style.id ? 'active' : ''}`}
                    >
                      <span className="style-icon">{style.icon}</span>
                      <span className="style-label">{style.label}</span>
                      {(selectedStyle[paper.id] || 'apa') === style.id && (
                        <motion.div
                          className="style-indicator"
                          layoutId={`style-indicator-${paper.id}`}
                          transition={{ type: "spring", stiffness: 500, damping: 30 }}
                        />
                      )}
                    </motion.button>
                  ))}
                </div>

                <div className="citation-text-wrapper">
                  <motion.div 
                    className="citation-text-box"
                    key={selectedStyle[paper.id] || 'apa'}
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ duration: 0.2 }}
                  >
                    <p className="citation-text">
                      {paper.citation[selectedStyle[paper.id] || 'apa'] || 'Citation not available for this style'}
                    </p>
                    <motion.button
                      whileHover={{ scale: 1.1 }}
                      whileTap={{ scale: 0.9 }}
                      onClick={() => copyToClipboard(
                        paper.citation[selectedStyle[paper.id] || 'apa'] || '',
                        paper.id
                      )}
                      className={`copy-citation-btn ${copiedId === paper.id ? 'copied' : ''}`}
                    >
                      <span className="copy-icon">{copiedId === paper.id ? '✓' : '📋'}</span>
                      <span className="copy-label">{copiedId === paper.id ? 'Copied!' : 'Copy'}</span>
                    </motion.button>
                  </motion.div>
                </div>
              </motion.div>
            )}

            {/* No Citation Available */}
            {!paper.citation && (
              <div className="no-citation">
                <span className="no-citation-icon">⚠️</span>
                <span className="no-citation-text">Citation data not available</span>
              </div>
            )}
          </motion.div>
        ))}
      </motion.div>

      {/* Empty State */}
      {papers.length === 0 && (
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          className="empty-citations"
        >
          <motion.div
            className="empty-glow"
            animate={{
              scale: [1, 1.2, 1],
              opacity: [0.3, 0.6, 0.3]
            }}
            transition={{
              duration: 3,
              repeat: Infinity,
              ease: "easeInOut"
            }}
          />
          <motion.span
            className="empty-icon"
            animate={{
              y: [0, -10, 0],
              rotateZ: [0, 5, -5, 0]
            }}
            transition={{
              duration: 3,
              repeat: Infinity,
              ease: "easeInOut"
            }}
          >
            🔗
          </motion.span>
          <h3 className="empty-title">No Citations Yet</h3>
          <p className="empty-subtitle">Add papers to generate citations</p>
        </motion.div>
      )}
    </div>
  )
}

export default CitationPanel
