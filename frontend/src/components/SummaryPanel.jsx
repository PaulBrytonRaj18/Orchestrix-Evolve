import React, { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import '../component.css'

const cardVariants = {
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

const expandVariants = {
  hidden: { 
    opacity: 0, 
    height: 0,
    marginTop: 0
  },
  visible: { 
    opacity: 1, 
    height: "auto",
    marginTop: "1rem",
    transition: {
      height: { type: "spring", stiffness: 100, damping: 15 },
      opacity: { duration: 0.3, delay: 0.1 }
    }
  },
  exit: {
    opacity: 0,
    height: 0,
    marginTop: 0,
    transition: {
      height: { duration: 0.2 },
      opacity: { duration: 0.15 }
    }
  }
}

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

  const selectAll = () => {
    if (selectedForSynthesis.length === papers.length) {
      setSelectedForSynthesis([])
    } else {
      setSelectedForSynthesis(papers.map(p => p.id))
    }
  }

  return (
    <div className="summary-panel">
      {/* Synthesis Control Bar */}
      <motion.div 
        className="synthesis-bar"
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
      >
        <div className="synthesis-bar-glow" />
        
        <div className="synthesis-info">
          <motion.div 
            className="selection-indicator"
            animate={{
              boxShadow: selectedForSynthesis.length >= 2 
                ? "0 0 20px rgba(220, 38, 38, 0.4)"
                : "0 0 10px rgba(220, 38, 38, 0.1)"
            }}
          >
            <span className="selection-count">{selectedForSynthesis.length}</span>
            <span className="selection-label">selected</span>
          </motion.div>
          
          <button 
            className="select-all-btn"
            onClick={selectAll}
          >
            {selectedForSynthesis.length === papers.length ? 'Deselect All' : 'Select All'}
          </button>
        </div>

        <motion.button
          className={`synthesize-btn ${selectedForSynthesis.length >= 2 ? 'active' : ''}`}
          onClick={() => onSynthesize && onSynthesize(selectedForSynthesis)}
          disabled={selectedForSynthesis.length < 2}
          whileHover={selectedForSynthesis.length >= 2 ? { 
            scale: 1.02,
            boxShadow: "0 0 30px rgba(220, 38, 38, 0.5)"
          } : {}}
          whileTap={selectedForSynthesis.length >= 2 ? { scale: 0.98 } : {}}
        >
          <span className="synthesize-icon">✨</span>
          <span>Synthesize Papers</span>
          {selectedForSynthesis.length >= 2 && (
            <motion.div 
              className="btn-glow"
              animate={{
                opacity: [0.5, 1, 0.5]
              }}
              transition={{
                duration: 2,
                repeat: Infinity,
                ease: "easeInOut"
              }}
            />
          )}
        </motion.button>
      </motion.div>

      {/* Papers List */}
      <motion.div 
        className="summary-papers-list"
        variants={containerVariants}
        initial="hidden"
        animate="visible"
      >
        {papers.map((paper, index) => (
          <motion.div
            key={paper.id}
            variants={cardVariants}
            className={`summary-card ${selectedForSynthesis.includes(paper.id) ? 'selected' : ''}`}
            whileHover={{ 
              scale: 1.005,
              y: -2,
              transition: { type: "spring", stiffness: 300 }
            }}
          >
            <div className="summary-card-glow" />
            
            {/* Card Header */}
            <div className="summary-card-header">
              <motion.label 
                className="checkbox-wrapper"
                whileHover={{ scale: 1.1 }}
                whileTap={{ scale: 0.9 }}
              >
                <input
                  type="checkbox"
                  checked={selectedForSynthesis.includes(paper.id)}
                  onChange={() => toggleForSynthesis(paper.id)}
                />
                <span className="checkbox-custom">
                  {selectedForSynthesis.includes(paper.id) && (
                    <motion.span 
                      className="checkmark"
                      initial={{ scale: 0 }}
                      animate={{ scale: 1 }}
                      transition={{ type: "spring", stiffness: 500 }}
                    >
                      ✓
                    </motion.span>
                  )}
                </span>
              </motion.label>

              <div className="summary-card-info">
                <h4 className="summary-card-title">{paper.title}</h4>
                <p className="summary-card-meta">
                  <span className="authors">
                    {paper.authors?.slice(0, 3).join(', ')}
                    {paper.authors?.length > 3 && ' et al.'}
                  </span>
                  <span className="separator">•</span>
                  <span className="year">{paper.year}</span>
                </p>
              </div>

              <motion.button
                className={`expand-btn ${expandedPapers[paper.id] ? 'expanded' : ''}`}
                onClick={() => toggleExpand(paper.id)}
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
              >
                <motion.span 
                  className="expand-icon"
                  animate={{ rotate: expandedPapers[paper.id] ? 180 : 0 }}
                  transition={{ duration: 0.2 }}
                >
                  ▼
                </motion.span>
                <span className="expand-text">
                  {expandedPapers[paper.id] ? 'Collapse' : 'Expand'}
                </span>
              </motion.button>
            </div>

            {/* Summary Content */}
            {paper.summary ? (
              <div className="summary-content">
                <div className="summary-section summary-abstract">
                  <div className="section-header">
                    <span className="section-icon">📝</span>
                    <h5 className="section-title">Summary</h5>
                  </div>
                  <p className="section-text">
                    {paper.summary.abstract_compression || 'No summary available.'}
                  </p>
                </div>

                <AnimatePresence>
                  {expandedPapers[paper.id] && (
                    <motion.div
                      className="expanded-content"
                      variants={expandVariants}
                      initial="hidden"
                      animate="visible"
                      exit="exit"
                    >
                      {paper.summary.key_contributions && (
                        <div className="summary-section">
                          <div className="section-header">
                            <span className="section-icon">🎯</span>
                            <h5 className="section-title">Key Contributions</h5>
                          </div>
                          <p className="section-text">
                            {paper.summary.key_contributions}
                          </p>
                        </div>
                      )}

                      {paper.summary.methodology && (
                        <div className="summary-section">
                          <div className="section-header">
                            <span className="section-icon">🔬</span>
                            <h5 className="section-title">Methodology</h5>
                          </div>
                          <p className="section-text">
                            {paper.summary.methodology}
                          </p>
                        </div>
                      )}

                      {paper.summary.limitations && (
                        <div className="summary-section">
                          <div className="section-header">
                            <span className="section-icon">⚠️</span>
                            <h5 className="section-title">Limitations</h5>
                          </div>
                          <p className="section-text">
                            {paper.summary.limitations}
                          </p>
                        </div>
                      )}
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            ) : (
              <div className="no-summary">
                <span className="no-summary-icon">📭</span>
                <span>Summary not available</span>
              </div>
            )}
          </motion.div>
        ))}
      </motion.div>

      {/* Empty State */}
      {papers.length === 0 && (
        <motion.div 
          className="summary-empty-state"
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
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
          <span className="empty-icon">✨</span>
          <p className="empty-title">No Papers Available</p>
          <p className="empty-subtitle">Papers with summaries will appear here</p>
        </motion.div>
      )}
    </div>
  )
}

export default SummaryPanel
