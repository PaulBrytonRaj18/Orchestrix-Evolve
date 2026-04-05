import React from 'react'
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend
} from 'recharts'

function AnalysisCharts({ analysis }) {
  if (!analysis) {
    return (
      <div style={{ color: '#64748b', fontStyle: 'italic', padding: '2rem' }}>
        Analysis not available. Run orchestration to generate analysis.
      </div>
    )
  }

  const chartColors = {
    primary: '#60a5fa',
    secondary: '#a78bfa',
    positive: '#22c55e',
    negative: '#ef4444'
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
      <div style={{ background: '#1e293b', padding: '1.5rem', borderRadius: '12px', border: '1px solid #334155' }}>
        <h3 style={{ color: '#f1f5f9', marginBottom: '1rem' }}>Publication Trend</h3>
        {analysis.publication_trend && analysis.publication_trend.length > 0 ? (
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={analysis.publication_trend}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis dataKey="year" stroke="#94a3b8" />
              <YAxis stroke="#94a3b8" />
              <Tooltip
                contentStyle={{ background: '#0f172a', border: '1px solid #334155', borderRadius: '8px' }}
                labelStyle={{ color: '#f1f5f9' }}
              />
              <Line
                type="monotone"
                dataKey="count"
                stroke={chartColors.primary}
                strokeWidth={2}
                dot={{ fill: chartColors.primary, r: 4 }}
              />
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <div style={{ color: '#64748b' }}>No publication data available</div>
        )}
      </div>

      <div style={{ background: '#1e293b', padding: '1.5rem', borderRadius: '12px', border: '1px solid #334155' }}>
        <h3 style={{ color: '#f1f5f9', marginBottom: '1rem' }}>Top Authors</h3>
        {analysis.top_authors && analysis.top_authors.length > 0 ? (
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={analysis.top_authors.slice(0, 15)} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis type="number" stroke="#94a3b8" />
              <YAxis type="category" dataKey="name" width={120} stroke="#94a3b8" tick={{ fontSize: 12 }} />
              <Tooltip
                contentStyle={{ background: '#0f172a', border: '1px solid #334155', borderRadius: '8px' }}
              />
              <Bar dataKey="count" fill={chartColors.secondary} />
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <div style={{ color: '#64748b' }}>No author data available</div>
        )}
      </div>

      <div style={{ background: '#1e293b', padding: '1.5rem', borderRadius: '12px', border: '1px solid #334155' }}>
        <h3 style={{ color: '#f1f5f9', marginBottom: '1rem' }}>Keyword Frequency (Top 20)</h3>
        {analysis.keyword_frequency && analysis.keyword_frequency.length > 0 ? (
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={analysis.keyword_frequency.slice(0, 20)}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis dataKey="word" stroke="#94a3b8" angle={-45} textAnchor="end" height={80} />
              <YAxis stroke="#94a3b8" />
              <Tooltip
                contentStyle={{ background: '#0f172a', border: '1px solid #334155', borderRadius: '8px' }}
              />
              <Bar dataKey="count" fill={chartColors.primary} />
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <div style={{ color: '#64748b' }}>No keyword data available</div>
        )}
      </div>

      <div style={{ background: '#1e293b', padding: '1.5rem', borderRadius: '12px', border: '1px solid #334155' }}>
        <h3 style={{ color: '#f1f5f9', marginBottom: '1rem' }}>Citation Distribution</h3>
        {analysis.citation_distribution && analysis.citation_distribution.length > 0 ? (
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={analysis.citation_distribution}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis dataKey="bucket" stroke="#94a3b8" />
              <YAxis stroke="#94a3b8" />
              <Tooltip
                contentStyle={{ background: '#0f172a', border: '1px solid #334155', borderRadius: '8px' }}
              />
              <Bar dataKey="count" fill={chartColors.secondary} />
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <div style={{ color: '#64748b' }}>No citation distribution data available</div>
        )}
      </div>

      <div style={{ background: '#1e293b', padding: '1.5rem', borderRadius: '12px', border: '1px solid #334155' }}>
        <h3 style={{ color: '#f1f5f9', marginBottom: '1rem' }}>Emerging Topics</h3>
        {analysis.emerging_topics && analysis.emerging_topics.length > 0 ? (
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={analysis.emerging_topics}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis dataKey="word" stroke="#94a3b8" angle={-45} textAnchor="end" height={80} />
              <YAxis stroke="#94a3b8" />
              <Tooltip
                contentStyle={{ background: '#0f172a', border: '1px solid #334155', borderRadius: '8px' }}
              />
              <Bar dataKey="delta" fill={chartColors.positive}>
                {analysis.emerging_topics.map((entry, index) => (
                  <rect key={index} fill={entry.delta >= 0 ? chartColors.positive : chartColors.negative} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <div style={{ color: '#64748b' }}>No emerging topics data available</div>
        )}
      </div>
    </div>
  )
}

export default AnalysisCharts
