import React from 'react'

function AgentTraceLog({ trace }) {
  if (!trace || trace.length === 0) {
    return (
      <div style={{
        padding: '1rem',
        color: '#64748b',
        fontStyle: 'italic'
      }}>
        No agent activity yet...
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
      {trace.map((entry, index) => (
        <div
          key={index}
          style={{
            display: 'flex',
            alignItems: 'flex-start',
            gap: '0.75rem',
            padding: '0.75rem 1rem',
            background: '#1e293b',
            borderRadius: '8px',
            borderLeft: `3px solid ${
              entry.status === 'done' ? '#22c55e' :
              entry.status === 'running' ? '#3b82f6' :
              entry.status === 'skipped' ? '#64748b' : '#64748b'
            }`
          }}
        >
          <div style={{ fontSize: '1.25rem' }}>
            {entry.status === 'done' && '✓'}
            {entry.status === 'running' && (
              <span style={{ animation: 'spin 1s linear infinite' }}>⟳</span>
            )}
            {entry.status === 'skipped' && '○'}
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: '600', color: '#e2e8f0' }}>
              {entry.agent}
            </div>
            <div style={{ 
              fontSize: '0.875rem',
              color: entry.status === 'skipped' ? '#64748b' : '#94a3b8'
            }}>
              {entry.status === 'running' && 'Running...'}
              {entry.status === 'done' && entry.result}
              {entry.status === 'skipped' && entry.reason}
            </div>
          </div>
        </div>
      ))}
      <style>{`
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  )
}

export default AgentTraceLog
