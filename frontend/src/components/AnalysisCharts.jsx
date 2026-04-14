import React from 'react'
import { motion } from 'framer-motion'
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend, Area, AreaChart, PieChart, Pie, Cell
} from 'recharts'
import { TrendingUp, Users, Tag, BookOpen, Zap } from 'lucide-react'

const CustomTooltip = ({ active, payload, label }) => {
  if (active && payload && payload.length) {
    return (
      <div className="card" style={{ padding: 'var(--space-3)', fontSize: 'var(--text-sm)' }}>
        <p style={{ fontWeight: 'var(--font-medium)', marginBottom: 'var(--space-1)' }}>{label}</p>
        {payload.map((entry, index) => (
          <p key={index} style={{ color: entry.color }}>
            {entry.name}: {typeof entry.value === 'number' ? entry.value.toLocaleString() : entry.value}
          </p>
        ))}
      </div>
    )
  }
  return null
}

function AnalysisCharts({ analysis }) {
  if (!analysis) {
    return (
      <div className="empty-state">
        <div className="empty-icon">
          <TrendingUp size={32} strokeWidth={1} />
        </div>
        <h3 className="empty-title">No analysis available</h3>
        <p className="empty-description">
          Run orchestration to generate analysis data
        </p>
      </div>
    )
  }

  const chartColors = {
    primary: 'var(--accent-primary)',
    secondary: 'var(--success-primary)',
    tertiary: 'var(--warning-primary)',
    grid: 'var(--border-primary)',
    text: 'var(--text-tertiary)'
  }

  const topAuthors = (analysis.top_authors || []).slice(0, 7)
  const maxAuthorCount = topAuthors.length > 0 ? Math.max(...topAuthors.map(a => a.count)) : 1

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-6)' }}>
      {/* Publication Trend */}
      {analysis.publication_trend?.length > 0 && (
        <div className="card" style={{ padding: 'var(--space-6)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', marginBottom: 'var(--space-4)' }}>
            <TrendingUp size={18} style={{ color: 'var(--accent-primary)' }} />
            <h3 style={{ fontSize: 'var(--text-lg)', fontWeight: 'var(--font-semibold)' }}>Publication Trend</h3>
          </div>
          <div style={{ height: '280px' }}>
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={analysis.publication_trend}>
                <defs>
                  <linearGradient id="pubGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={chartColors.primary} stopOpacity={0.3} />
                    <stop offset="100%" stopColor={chartColors.primary} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke={chartColors.grid} />
                <XAxis dataKey="year" stroke={chartColors.text} fontSize={12} />
                <YAxis stroke={chartColors.text} fontSize={12} />
                <Tooltip content={<CustomTooltip />} />
                <Area type="monotone" dataKey="count" stroke={chartColors.primary} strokeWidth={2} fill="url(#pubGradient)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Top Authors */}
      {topAuthors.length > 0 && (
        <div className="card" style={{ padding: 'var(--space-6)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', marginBottom: 'var(--space-4)' }}>
            <Users size={18} style={{ color: 'var(--accent-primary)' }} />
            <h3 style={{ fontSize: 'var(--text-lg)', fontWeight: 'var(--font-semibold)' }}>Top Authors</h3>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
            {topAuthors.map((author, index) => (
              <div key={author.name || index} style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
                <div style={{ 
                  width: '28px', 
                  height: '28px', 
                  borderRadius: 'var(--radius-full)', 
                  background: 'var(--accent-subtle)', 
                  color: 'var(--accent-primary)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: 'var(--text-xs)',
                  fontWeight: 'var(--font-semibold)',
                  flexShrink: 0
                }}>
                  {index + 1}
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                    <span style={{ fontSize: 'var(--text-sm)', fontWeight: 'var(--font-medium)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {author.name}
                    </span>
                    <span style={{ fontSize: 'var(--text-sm)', color: 'var(--text-tertiary)', marginLeft: 'var(--space-2)' }}>
                      {author.count} papers
                    </span>
                  </div>
                  <div style={{ height: '4px', background: 'var(--bg-tertiary)', borderRadius: 'var(--radius-full)', overflow: 'hidden' }}>
                    <div style={{ 
                      height: '100%', 
                      width: `${(author.count / maxAuthorCount) * 100}%`,
                      background: 'var(--accent-primary)',
                      borderRadius: 'var(--radius-full)'
                    }} />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Keywords */}
      {analysis.keyword_frequency?.length > 0 && (
        <div className="card" style={{ padding: 'var(--space-6)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', marginBottom: 'var(--space-4)' }}>
            <Tag size={18} style={{ color: 'var(--accent-primary)' }} />
            <h3 style={{ fontSize: 'var(--text-lg)', fontWeight: 'var(--font-semibold)' }}>Keywords</h3>
          </div>
          <div style={{ height: '300px' }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={analysis.keyword_frequency.slice(0, 15)} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke={chartColors.grid} horizontal={false} />
                <XAxis type="number" stroke={chartColors.text} fontSize={12} />
                <YAxis dataKey="word" type="category" stroke={chartColors.text} fontSize={11} width={100} />
                <Tooltip content={<CustomTooltip />} />
                <Bar dataKey="count" fill={chartColors.primary} radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Citation Distribution */}
      {analysis.citation_distribution?.length > 0 && (
        <div className="card" style={{ padding: 'var(--space-6)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', marginBottom: 'var(--space-4)' }}>
            <BookOpen size={18} style={{ color: 'var(--accent-primary)' }} />
            <h3 style={{ fontSize: 'var(--text-lg)', fontWeight: 'var(--font-semibold)' }}>Citation Distribution</h3>
          </div>
          <div style={{ height: '280px' }}>
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={analysis.citation_distribution}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={100}
                  paddingAngle={2}
                  dataKey="count"
                  nameKey="bucket"
                >
                  {analysis.citation_distribution.map((entry, index) => (
                    <Cell key={index} fill={[
                      'var(--accent-primary)',
                      'var(--accent-secondary)',
                      'var(--success-primary)',
                      'var(--warning-primary)',
                      'var(--text-tertiary)'
                    ][index % 5]} />
                  ))}
                </Pie>
                <Tooltip content={<CustomTooltip />} />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Emerging Topics */}
      {analysis.emerging_topics?.length > 0 && (
        <div className="card" style={{ padding: 'var(--space-6)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', marginBottom: 'var(--space-4)' }}>
            <Zap size={18} style={{ color: 'var(--success-primary)' }} />
            <h3 style={{ fontSize: 'var(--text-lg)', fontWeight: 'var(--font-semibold)' }}>Emerging Topics</h3>
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-2)' }}>
            {analysis.emerging_topics.map((topic, index) => (
              <span key={index} className="badge badge-success" style={{ fontSize: 'var(--text-sm)', padding: 'var(--space-2) var(--space-3)' }}>
                {topic.word}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export default AnalysisCharts
