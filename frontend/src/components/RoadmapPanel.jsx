import React, { useState } from 'react'
import { motion } from 'framer-motion'
import { api } from '../api.js'

function RoadmapPanel({ roadmap, sessionId, onQueryClick }) {
  const [isGenerating, setIsGenerating] = useState(false)

  const generateRoadmap = async () => {
    setIsGenerating(true)
    try {
      const newRoadmap = await api.generateRoadmap(sessionId)
      window.location.reload()
    } catch (error) {
      console.error('Error generating roadmap:', error)
      setIsGenerating(false)
    }
  }

  if (!roadmap) {
    return (
      <div className="roadmap-empty">
        <span className="empty-icon">🗺️</span>
        <p>No roadmap generated yet</p>
        <button 
          onClick={generateRoadmap} 
          disabled={isGenerating}
          className="generate-roadmap-btn"
        >
          {isGenerating ? 'Generating...' : 'Generate Roadmap'}
        </button>
      </div>
    )
  }

  return (
    <div className="roadmap-container">
      <div className="roadmap-header">
        <h2>Research Roadmap</h2>
        <button 
          onClick={generateRoadmap} 
          disabled={isGenerating}
          className="regenerate-btn"
        >
          {isGenerating ? 'Regenerating...' : '🔄 Regenerate'}
        </button>
      </div>

      <section className="roadmap-section foundational-papers">
        <h3>📚 Foundational Papers</h3>
        <p className="section-description">
          Papers ranked by citation impact and recency
        </p>
        {roadmap.foundational_papers && roadmap.foundational_papers.length > 0 ? (
          <div className="papers-grid">
            {roadmap.foundational_papers.map((paper, idx) => (
              <motion.div
                key={paper.paper_id || idx}
                className="foundational-paper-card"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: idx * 0.1 }}
              >
                <div className="priority-badge">#{paper.priority}</div>
                <h4>{paper.title}</h4>
                <div className="paper-meta">
                  <span>{paper.year}</span>
                  <span>{paper.citation_count} citations</span>
                </div>
                <p className="paper-reason">{paper.reason}</p>
              </motion.div>
            ))}
          </div>
        ) : (
          <p className="no-data">No foundational papers identified yet</p>
        )}
      </section>

      <section className="roadmap-section gap-areas">
        <h3>🔍 Research Gaps</h3>
        <p className="section-description">
          Unanswered questions identified across your research collection
        </p>
        {roadmap.gap_areas && roadmap.gap_areas.length > 0 ? (
          <div className="gaps-list">
            {roadmap.gap_areas.map((gap, idx) => (
              <motion.div
                key={idx}
                className={`gap-card severity-${gap.severity}`}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: idx * 0.1 }}
              >
                <div className="gap-header">
                  <span className={`severity-badge ${gap.severity}`}>
                    {gap.severity.toUpperCase()}
                  </span>
                  <h4>{gap.question}</h4>
                </div>
                <p className="gap-evidence">{gap.evidence}</p>
                {gap.related_papers && gap.related_papers.length > 0 && (
                  <div className="related-papers">
                    <span>Related to {gap.related_papers.length} paper(s)</span>
                  </div>
                )}
              </motion.div>
            ))}
          </div>
        ) : (
          <p className="no-data">No research gaps identified yet</p>
        )}
      </section>

      <section className="roadmap-section query-suggestions">
        <h3>🎯 Next Steps</h3>
        <p className="section-description">
          Click any suggestion to run a new search
        </p>
        {roadmap.next_query_suggestions && roadmap.next_query_suggestions.length > 0 ? (
          <div className="queries-list">
            {roadmap.next_query_suggestions.map((q, idx) => (
              <motion.button
                key={idx}
                className="query-suggestion-btn"
                onClick={() => onQueryClick(q.query)}
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: idx * 0.1 }}
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
              >
                <div className="query-main">
                  <span className="query-icon">🔍</span>
                  <span className="query-text">{q.query}</span>
                </div>
                <div className="query-details">
                  <span className="query-rationale">{q.rationale}</span>
                  <span className="query-insight">Expected: {q.expected_insight}</span>
                </div>
                <span className="click-hint">Click to search →</span>
              </motion.button>
            ))}
          </div>
        ) : (
          <p className="no-data">No query suggestions available</p>
        )}
      </section>
    </div>
  )
}

export default RoadmapPanel
