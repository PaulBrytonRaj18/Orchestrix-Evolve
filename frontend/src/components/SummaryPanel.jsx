import React, { useState } from 'react'
import { motion } from 'framer-motion'
import { Sparkles, ChevronDown, ChevronUp } from 'lucide-react'

function SummaryPanel({ papers, sessionId, onSynthesize }) {
  const [expandedPapers, setExpandedPapers] = useState({})
  const [selectedForSynthesis, setSelectedForSynthesis] = useState([])

  const toggleExpand = (paperId) => {
    setExpandedPapers(prev => ({ ...prev, [paperId]: !prev[paperId] }))
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

  if (!papers || papers.length === 0) {
    return (
      <div className="empty-state">
        <div className="empty-icon">
          <Sparkles size={32} strokeWidth={1} />
        </div>
        <h3 className="empty-title">No papers to summarize</h3>
        <p className="empty-description">
          Add papers to your session to view and synthesize summaries
        </p>
      </div>
    )
  }

  return (
    <div>
      {/* Synthesis Bar */}
      <div style={{ 
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'space-between',
        padding: 'var(--space-4)',
        background: 'var(--bg-secondary)',
        borderRadius: 'var(--radius-lg)',
        marginBottom: 'var(--space-6)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
          <span style={{ 
            display: 'flex', 
            alignItems: 'center', 
            justifyContent: 'center',
            width: '28px',
            height: '28px',
            background: 'var(--accent-primary)',
            color: 'white',
            borderRadius: 'var(--radius-full)',
            fontSize: 'var(--text-sm)',
            fontWeight: 'var(--font-semibold)'
          }}>
            {selectedForSynthesis.length}
          </span>
          <span style={{ fontSize: 'var(--text-sm)', color: 'var(--text-secondary)' }}>
            selected for synthesis
          </span>
        </div>
        <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
          <button className="btn btn-ghost btn-sm" onClick={selectAll}>
            {selectedForSynthesis.length === papers.length ? 'Deselect All' : 'Select All'}
          </button>
          <button
            className="btn btn-primary"
            disabled={selectedForSynthesis.length < 2}
            onClick={() => onSynthesize && onSynthesize(selectedForSynthesis)}
          >
            <Sparkles size={14} />
            Synthesize
          </button>
        </div>
      </div>

      {/* Papers List */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
        {papers.map((paper) => (
          <div key={paper.id} className="card" style={{ padding: 'var(--space-5)' }}>
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: 'var(--space-3)' }}>
              <input
                type="checkbox"
                checked={selectedForSynthesis.includes(paper.id)}
                onChange={() => toggleForSynthesis(paper.id)}
                style={{ marginTop: '4px' }}
              />
              <div style={{ flex: 1 }}>
                <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 'var(--space-4)', marginBottom: 'var(--space-2)' }}>
                  <div>
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
                    onClick={() => toggleExpand(paper.id)}
                  >
                    {expandedPapers[paper.id] ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                  </button>
                </div>

                {paper.summary && (
                  <div style={{ marginTop: 'var(--space-3)' }}>
                    {paper.summary.abstract_compression && (
                      <div style={{ marginBottom: 'var(--space-3)' }}>
                        <h5 style={{ fontSize: 'var(--text-xs)', fontWeight: 'var(--font-semibold)', color: 'var(--text-tertiary)', marginBottom: 'var(--space-1)', textTransform: 'uppercase' }}>
                          Summary
                        </h5>
                        <p style={{ fontSize: 'var(--text-sm)', color: 'var(--text-secondary)', lineHeight: 'var(--leading-relaxed)' }}>
                          {paper.summary.abstract_compression}
                        </p>
                      </div>
                    )}
                    
                    {expandedPapers[paper.id] && (
                      <motion.div
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: 'auto' }}
                        style={{ marginTop: 'var(--space-3)', paddingTop: 'var(--space-3)', borderTop: '1px solid var(--card-border)' }}
                      >
                        {paper.summary.key_contributions && (
                          <div style={{ marginBottom: 'var(--space-3)' }}>
                            <h5 style={{ fontSize: 'var(--text-xs)', fontWeight: 'var(--font-semibold)', color: 'var(--text-tertiary)', marginBottom: 'var(--space-1)', textTransform: 'uppercase' }}>
                              Key Contributions
                            </h5>
                            <p style={{ fontSize: 'var(--text-sm)', color: 'var(--text-secondary)' }}>
                              {paper.summary.key_contributions}
                            </p>
                          </div>
                        )}
                        {paper.summary.methodology && (
                          <div style={{ marginBottom: 'var(--space-3)' }}>
                            <h5 style={{ fontSize: 'var(--text-xs)', fontWeight: 'var(--font-semibold)', color: 'var(--text-tertiary)', marginBottom: 'var(--space-1)', textTransform: 'uppercase' }}>
                              Methodology
                            </h5>
                            <p style={{ fontSize: 'var(--text-sm)', color: 'var(--text-secondary)' }}>
                              {paper.summary.methodology}
                            </p>
                          </div>
                        )}
                        {paper.summary.limitations && (
                          <div>
                            <h5 style={{ fontSize: 'var(--text-xs)', fontWeight: 'var(--font-semibold)', color: 'var(--text-tertiary)', marginBottom: 'var(--space-1)', textTransform: 'uppercase' }}>
                              Limitations
                            </h5>
                            <p style={{ fontSize: 'var(--text-sm)', color: 'var(--text-secondary)' }}>
                              {paper.summary.limitations}
                            </p>
                          </div>
                        )}
                      </motion.div>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

export default SummaryPanel
