import React from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import '../component.css'
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend, Area, AreaChart, PieChart, Pie, Cell,
  RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar
} from 'recharts'

const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.15,
      delayChildren: 0.1
    }
  }
}

const cardVariants = {
  hidden: { opacity: 0, y: 30, scale: 0.95 },
  visible: {
    opacity: 1,
    y: 0,
    scale: 1,
    transition: {
      type: "spring",
      stiffness: 100,
      damping: 15
    }
  }
}

const CustomTooltip = ({ active, payload, label }) => {
  if (active && payload && payload.length) {
    return (
      <div className="chart-tooltip">
        <p className="tooltip-label">{label}</p>
        {payload.map((entry, index) => (
          <p key={index} className="tooltip-value" style={{ color: entry.color }}>
            {entry.name}: <span>{typeof entry.value === 'number' ? entry.value.toLocaleString() : entry.value}</span>
          </p>
        ))}
      </div>
    )
  }
  return null
}

const AUTHOR_COLORS = [
  '#dc2626', '#ef4444', '#f87171', '#fca5a5', '#fecaca',
  '#991b1b', '#b91c1c', '#c81e1e', '#dc2626', '#e53e3e'
]

function AuthorCard({ author, index, maxCount }) {
  const percentage = Math.round((author.count / maxCount) * 100)
  const initials = author.name
    .split(' ')
    .map(n => n[0])
    .join('')
    .toUpperCase()
    .slice(0, 2)
  
  return (
    <motion.div
      className="author-card"
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.1 }}
      whileHover={{ scale: 1.02, x: 4 }}
    >
      <div className="author-rank" style={{ background: AUTHOR_COLORS[index % AUTHOR_COLORS.length] }}>
        {index + 1}
      </div>
      <div className="author-avatar" style={{ background: `${AUTHOR_COLORS[index % AUTHOR_COLORS.length]}20`, color: AUTHOR_COLORS[index % AUTHOR_COLORS.length] }}>
        {initials}
      </div>
      <div className="author-info">
        <h4 className="author-name">{author.name.length > 25 ? author.name.slice(0, 25) + '...' : author.name}</h4>
        <div className="author-stats">
          <span className="paper-count">{author.count} paper{author.count !== 1 ? 's' : ''}</span>
          <div className="author-bar-container">
            <div 
              className="author-bar-fill" 
              style={{ 
                width: `${percentage}%`,
                background: `linear-gradient(90deg, ${AUTHOR_COLORS[index % AUTHOR_COLORS.length]} 0%, ${AUTHOR_COLORS[index % AUTHOR_COLORS.length]}80 100%)`
              }}
            />
          </div>
        </div>
      </div>
    </motion.div>
  )
}

function CitationPieChart({ data }) {
  const COLORS = ['#dc2626', '#ef4444', '#f87171', '#fca5a5', '#991b1b', '#b91c1c']
  
  const RADIAN = Math.PI / 180
  const renderCustomizedLabel = ({ cx, cy, midAngle, innerRadius, outerRadius, percent, index }) => {
    if (percent < 0.05) return null
    const radius = innerRadius + (outerRadius - innerRadius) * 0.5
    const x = cx + radius * Math.cos(-midAngle * RADIAN)
    const y = cy + radius * Math.sin(-midAngle * RADIAN)
    
    return (
      <text x={x} y={y} fill="white" textAnchor="middle" dominantBaseline="central" fontSize={12} fontWeight="600">
        {`${(percent * 100).toFixed(0)}%`}
      </text>
    )
  }

  return (
    <ResponsiveContainer width="100%" height={280}>
      <PieChart>
        <Pie
          data={data}
          cx="50%"
          cy="50%"
          labelLine={false}
          label={renderCustomizedLabel}
          outerRadius={100}
          innerRadius={50}
          fill="#8884d8"
          dataKey="count"
          nameKey="bucket"
          paddingAngle={2}
        >
          {data.map((entry, index) => (
            <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
          ))}
        </Pie>
        <Tooltip content={<CustomTooltip />} />
        <Legend 
          layout="vertical" 
          align="right" 
          verticalAlign="middle"
          formatter={(value, entry) => (
            <span style={{ color: '#a1a1aa', fontSize: '12px' }}>{value}</span>
          )}
        />
      </PieChart>
    </ResponsiveContainer>
  )
}

function CitationDonutWithStats({ data }) {
  const total = data.reduce((acc, curr) => acc + curr.count, 0)
  const COLORS = ['#dc2626', '#ef4444', '#f87171', '#fca5a5', '#991b1b', '#b91c1c']
  
  const formatLabel = (bucket) => {
    if (bucket.includes('-')) {
      return bucket.split('-').map(n => n.includes('K') ? n : n).join(' - ')
    }
    return bucket
  }

  return (
    <div className="citation-stats-container">
      <div className="citation-donut-wrapper">
        <ResponsiveContainer width="100%" height={220}>
          <PieChart>
            <Pie
              data={data}
              cx="50%"
              cy="50%"
              innerRadius={55}
              outerRadius={85}
              paddingAngle={3}
              dataKey="count"
              nameKey="bucket"
            >
              {data.map((entry, index) => (
                <Cell 
                  key={`cell-${index}`} 
                  fill={COLORS[index % COLORS.length]}
                  stroke="transparent"
                />
              ))}
            </Pie>
            <Tooltip content={<CustomTooltip />} />
          </PieChart>
        </ResponsiveContainer>
        <div className="citation-center-stat">
          <span className="stat-value">{total}</span>
          <span className="stat-label">Total Papers</span>
        </div>
      </div>
      
      <div className="citation-legend">
        {data.map((entry, index) => (
          <div key={index} className="citation-legend-item">
            <div className="legend-color" style={{ background: COLORS[index % COLORS.length] }} />
            <span className="legend-label">{formatLabel(entry.bucket)}</span>
            <span className="legend-count">{entry.count} ({((entry.count / total) * 100).toFixed(1)}%)</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function AnalysisCharts({ analysis }) {
  if (!analysis) {
    return (
      <motion.div
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        className="analysis-empty"
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
            rotateY: [0, 360]
          }}
          transition={{
            y: { duration: 2, repeat: Infinity, ease: "easeInOut" },
            rotateY: { duration: 4, repeat: Infinity, ease: "linear" }
          }}
        >
          📊
        </motion.span>
        <h3>Analysis Not Available</h3>
        <p>Run orchestration to generate analysis data</p>
      </motion.div>
    )
  }

  const chartColors = {
    primary: '#dc2626',
    primaryLight: '#ef4444',
    secondary: '#f87171',
    gradient: ['#dc2626', '#7f1d1d'],
    positive: '#22c55e',
    negative: '#ef4444',
    grid: 'rgba(220, 38, 38, 0.1)',
    axis: '#71717a',
    text: '#a1a1aa'
  }

  const topAuthors = (analysis.top_authors || []).slice(0, 7)
  const maxAuthorCount = topAuthors.length > 0 ? Math.max(...topAuthors.map(a => a.count)) : 1

  const CitationDistribution = () => (
    <div className="citation-distribution-wrapper">
      {analysis.citation_distribution && analysis.citation_distribution.length > 0 ? (
        <CitationDonutWithStats data={analysis.citation_distribution} />
      ) : (
        <div className="chart-no-data">
          <span className="no-data-icon">📭</span>
          <p>No citation data available</p>
        </div>
      )}
    </div>
  )

  const TopAuthorsChart = () => (
    <div className="top-authors-wrapper">
      {topAuthors.length > 0 ? (
        <div className="authors-list">
          {topAuthors.map((author, index) => (
            <AuthorCard 
              key={author.name || index} 
              author={author} 
              index={index}
              maxCount={maxAuthorCount}
            />
          ))}
        </div>
      ) : (
        <div className="chart-no-data">
          <span className="no-data-icon">👤</span>
          <p>No author data available</p>
        </div>
      )}
    </div>
  )

  const charts = [
    {
      id: 'publication',
      title: 'Publication Trend',
      icon: '📈',
      subtitle: 'Papers per Year',
      data: analysis.publication_trend,
      render: (data) => (
        <ResponsiveContainer width="100%" height={280}>
          <AreaChart data={data}>
            <defs>
              <linearGradient id="publicationGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={chartColors.primary} stopOpacity={0.4} />
                <stop offset="100%" stopColor={chartColors.primary} stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke={chartColors.grid} />
            <XAxis 
              dataKey="year" 
              stroke={chartColors.axis}
              tick={{ fill: chartColors.text, fontSize: 12 }}
              axisLine={{ stroke: chartColors.grid }}
            />
            <YAxis 
              stroke={chartColors.axis}
              tick={{ fill: chartColors.text, fontSize: 12 }}
              axisLine={{ stroke: chartColors.grid }}
            />
            <Tooltip content={<CustomTooltip />} />
            <Area
              type="monotone"
              dataKey="count"
              stroke={chartColors.primary}
              strokeWidth={3}
              fill="url(#publicationGradient)"
              dot={{ fill: chartColors.primary, strokeWidth: 2, r: 4, stroke: '#0a0a0a' }}
              activeDot={{ r: 6, stroke: chartColors.primaryLight, strokeWidth: 2 }}
            />
          </AreaChart>
        </ResponsiveContainer>
      )
    },
    {
      id: 'authors',
      title: 'Top Authors',
      icon: '👥',
      subtitle: 'Most Prolific Researchers',
      data: topAuthors,
      render: () => <TopAuthorsChart />,
      isCustom: true
    },
    {
      id: 'keywords',
      title: 'Keyword Frequency',
      icon: '🏷️',
      subtitle: 'Top 15 Keywords',
      data: analysis.keyword_frequency,
      render: (data) => (
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={data.slice(0, 15)}>
            <defs>
              <linearGradient id="keywordGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={chartColors.primary} />
                <stop offset="100%" stopColor={chartColors.gradient[1]} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke={chartColors.grid} vertical={false} />
            <XAxis 
              dataKey="word" 
              stroke={chartColors.axis}
              tick={{ fill: chartColors.text, fontSize: 10 }}
              angle={-40}
              textAnchor="end"
              height={80}
              axisLine={{ stroke: chartColors.grid }}
            />
            <YAxis 
              stroke={chartColors.axis}
              tick={{ fill: chartColors.text, fontSize: 12 }}
              axisLine={{ stroke: chartColors.grid }}
            />
            <Tooltip content={<CustomTooltip />} />
            <Bar 
              dataKey="count" 
              fill="url(#keywordGradient)"
              radius={[4, 4, 0, 0]}
            />
          </BarChart>
        </ResponsiveContainer>
      )
    },
    {
      id: 'citations',
      title: 'Citation Distribution',
      icon: '📚',
      subtitle: 'Papers by Citation Count',
      data: analysis.citation_distribution,
      render: () => <CitationDistribution />,
      isCustom: true
    },
    {
      id: 'emerging',
      title: 'Emerging Topics',
      icon: '🚀',
      subtitle: 'Trending Keywords',
      data: analysis.emerging_topics,
      render: (data) => (
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={data}>
            <defs>
              <linearGradient id="positiveGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#22c55e" />
                <stop offset="100%" stopColor="#166534" />
              </linearGradient>
              <linearGradient id="negativeGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#ef4444" />
                <stop offset="100%" stopColor="#7f1d1d" />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke={chartColors.grid} vertical={false} />
            <XAxis 
              dataKey="word" 
              stroke={chartColors.axis}
              tick={{ fill: chartColors.text, fontSize: 10 }}
              angle={-40}
              textAnchor="end"
              height={80}
              axisLine={{ stroke: chartColors.grid }}
            />
            <YAxis 
              stroke={chartColors.axis}
              tick={{ fill: chartColors.text, fontSize: 12 }}
              axisLine={{ stroke: chartColors.grid }}
            />
            <Tooltip content={<CustomTooltip />} />
            <Bar 
              dataKey="delta"
              radius={[4, 4, 0, 0]}
              fill={chartColors.positive}
            >
              {data.map((entry, index) => (
                <rect 
                  key={index} 
                  fill={entry.delta >= 0 ? 'url(#positiveGradient)' : 'url(#negativeGradient)'} 
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      )
    }
  ]

  return (
    <motion.div
      className="analysis-container"
      variants={containerVariants}
      initial="hidden"
      animate="visible"
    >
      {charts.map((chart, index) => (
        <motion.div
          key={chart.id}
          className={`chart-card ${chart.isCustom ? 'chart-card-custom' : ''}`}
          variants={cardVariants}
          whileHover={{ 
            boxShadow: "0 8px 40px rgba(220, 38, 38, 0.2), 0 4px 30px rgba(0, 0, 0, 0.5)",
            borderColor: "rgba(220, 38, 38, 0.4)",
            transition: { duration: 0.2 }
          }}
        >
          <motion.div 
            className="chart-card-glow"
            animate={{
              opacity: [0.3, 0.5, 0.3]
            }}
            transition={{
              duration: 3 + index * 0.5,
              repeat: Infinity,
              ease: "easeInOut"
            }}
          />
          
          <div className="chart-header">
            <div className="chart-title-wrapper">
              <motion.span 
                className="chart-icon"
                whileHover={{ scale: 1.15 }}
              >
                {chart.icon}
              </motion.span>
              <div>
                <h3 className="chart-title">{chart.title}</h3>
                {chart.subtitle && (
                  <span className="chart-subtitle">{chart.subtitle}</span>
                )}
              </div>
            </div>
            {chart.data && chart.data.length > 0 && !chart.isCustom && (
              <motion.div 
                className="chart-badge"
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ type: "spring", stiffness: 500, delay: 0.3 + index * 0.1 }}
              >
                {chart.data.length} items
              </motion.div>
            )}
          </div>

          <div className="chart-content">
            {chart.data && chart.data.length > 0 ? (
              chart.render(chart.data)
            ) : (
              <div className="chart-no-data">
                <span className="no-data-icon">📭</span>
                <p>No data available</p>
              </div>
            )}
          </div>
        </motion.div>
      ))}
    </motion.div>
  )
}

export default AnalysisCharts
