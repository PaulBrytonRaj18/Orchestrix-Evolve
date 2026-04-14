import React, { useState } from 'react'
import { motion } from 'framer-motion'
import { api } from '../api.js'
import { Map, FileText, RefreshCw, Search, ArrowRight } from 'lucide-react'

function RoadmapPanel({ roadmap, sessionId, onQueryClick }) {
  const [isGenerating, setIsGenerating] = useState(false)

  const generateRoadmap = async () => {
    setIsGenerating(true)
    try {
      await api.generateRoadmap(sessionId)
      window.location.reload()
    } catch (error) {
      console.error('Error generating roadmap:', error)
      setIsGenerating(false)
    }
  }

  if (!roadmap) {
    return (
      <div className="empty-state">
        <div className="empty-icon">
          <Map size={32} strokeWidth={1} />
        </div>
        <h3 className="empty-title">No roadmap generated</h3>
        <p className="empty-description">
          Generate a roadmap to see research directions and insights
        </p>
        <button
          className="btn btn-primary"
          onClick={generateRoadmap}
          disabled={isGenerating}
          style={{ marginTop: 'var(--space-4)' }}
        >
          {isGenerating ? <RefreshCw size={14} style={{ animation: 'spin 0.8s linear infinite' }} /> : <Map size={14} />}
          Generate Roadmap
        </button>
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-8)' }}>
      {/* Foundational Papers */}
      {roadmap.foundational_papers?.length > 0 && (
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', marginBottom: 'var(--space-4)' }}>
            <FileText size={18} style={{ color: 'var(--accent-primary)' }} />
            <h3 style={{ fontSize: 'var(--text-lg)', fontWeight: 'var(--font-semibold)' }}>Foundational Papers</h3>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: 'var(--space-3)' }}>
            {roadmap.foundational_papers.slice(0, 6).map((paper, idx) => (
              <motion.div
                key={paper.paper_id || idx}
                className="card card-hover"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: idx * 0.05 }}
                style={{ padding: 'var(--space-4)' }}
              >
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: 'var(--space-3)' }}>
                  <div style={{
                    width: '24px',
                    height: '24px',
                    borderRadius: 'var(--radius-full)',
                    background: 'var(--accent-subtle)',
                    color: 'var(--accent-primary)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: 'var(--text-xs)',
                    fontWeight: 'var(--font-bold)',
                    flexShrink: 0
                  }}>
                    {paper.priority}
                  </div>
                  <div>
                    <h4 style={{ fontSize: 'var(--text-sm)', fontWeight: 'var(--font-medium)', marginBottom: 'var(--space-1)', lineHeight: 'var(--leading-tight)' }}>
                      {paper.title}
                    </h4>
                    <p style={{ fontSize: 'var(--text-xs)', color: 'var(--text-tertiary)', marginBottom: 'var(--space-2)' }}>
                      {paper.year} • {paper.citation_count} citations
                    </p>
                    {paper.reason && (
                      <p style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>
                        {paper.reason}
                      </p>
                    )}
                  </div>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      )}

      {/* Research Gaps */}
      {roadmap.gap_areas?.length > 0 && (
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', marginBottom: 'var(--space-4)' }}>
            <Search size={18} style={{ color: 'var(--warning-primary)' }} />
            <h3 style={{ fontSize: 'var(--text-lg)', fontWeight: 'var(--font-semibold)' }}>Research Gaps</h3>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
            {roadmap.gap_areas.map((gap, idx) => (
              <div key={idx} className="card" style={{ padding: 'var(--space-4)' }}>
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: 'var(--space-3)' }}>
                  <span className={`badge badge-${gap.severity === 'high' ? 'error' : gap.severity === 'medium' ? 'warning' : 'default'}`}>
                    {gap.severity}
                  </span>
                  <div>
                    <h4 style={{ fontSize: 'var(--text-sm)', fontWeight: 'var(--font-medium)', marginBottom: 'var(--space-1)' }}>
                      {gap.question}
                    </h4>
                    {gap.evidence && (
                      <p style={{ fontSize: 'var(--text-sm)', color: 'var(--text-secondary)' }}>
                        {gap.evidence}
                      </p>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Next Steps */}
      {roadmap.next_query_suggestions?.length > 0 && (
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', marginBottom: 'var(--space-4)' }}>
            <ArrowRight size={18} style={{ color: 'var(--success-primary)' }} />
            <h3 style={{ fontSize: 'var(--text-lg)', fontWeight: 'var(--font-semibold)' }}>Suggested Research</h3>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
            {roadmap.next_query_suggestions.map((q, idx) => (
              <motion.button
                key={idx}
                className="card card-hover"
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: idx * 0.05 }}
                onClick={() => onQueryClick && onQueryClick(q.query)}
                style={{ 
                  padding: 'var(--space-4)', 
                  textAlign: 'left',
                  width: '100%',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 'var(--space-2)'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span style={{ fontSize: 'var(--text-sm)', fontWeight: 'var(--font-medium)' }}>
                    {q.query}
                  </span>
                  <ArrowRight size={14} style={{ color: 'var(--text-tertiary)' }} />
                </div>
                {q.rationale && (
                  <p style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>
                    {q.rationale}
                  </p>
                )}
              </motion.button>
            ))}
          </div>
        </div>
      )}

      {/* Regenerate Button */}
      <div style={{ display: 'flex', justifyContent: 'center', paddingTop: 'var(--space-4)' }}>
        <button
          className="btn btn-secondary"
          onClick={generateRoadmap}
          disabled={isGenerating}
        >
          {isGenerating ? <RefreshCw size={14} style={{ animation: 'spin 0.8s linear infinite' }} /> : <RefreshCw size={14} />}
          Regenerate Roadmap
        </button>
      </div>
    </div>
  )
}

export default RoadmapPanel
