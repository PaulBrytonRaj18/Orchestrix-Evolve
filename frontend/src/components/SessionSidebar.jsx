import React from 'react'

function SessionSidebar({ sessions, currentSessionId, onSelectSession }) {
  const formatRelativeTime = (dateString) => {
    const date = new Date(dateString)
    const now = new Date()
    const diffMs = now - date
    const diffMins = Math.floor(diffMs / 60000)
    const diffHours = Math.floor(diffMs / 3600000)
    const diffDays = Math.floor(diffMs / 86400000)

    if (diffMins < 1) return 'Just now'
    if (diffMins < 60) return `${diffMins}m ago`
    if (diffHours < 24) return `${diffHours}h ago`
    if (diffDays < 7) return `${diffDays}d ago`
    return date.toLocaleDateString()
  }

  return (
    <div style={{
      width: '280px',
      background: '#1e293b',
      borderRadius: '12px',
      padding: '1rem',
      height: 'fit-content',
      maxHeight: 'calc(100vh - 200px)',
      overflow: 'auto',
      border: '1px solid #334155'
    }}>
      <h3 style={{ color: '#f1f5f9', marginBottom: '1rem', fontSize: '1rem' }}>
        Past Sessions
      </h3>

      {sessions.length === 0 ? (
        <div style={{ color: '#64748b', fontStyle: 'italic', padding: '1rem 0' }}>
          No sessions yet
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
          {sessions.map((session) => (
            <button
              key={session.id}
              onClick={() => onSelectSession(session.id)}
              style={{
                background: currentSessionId === session.id ? '#334155' : 'transparent',
                border: currentSessionId === session.id ? '1px solid #60a5fa' : '1px solid transparent',
                borderRadius: '8px',
                padding: '0.75rem',
                cursor: 'pointer',
                textAlign: 'left',
                transition: 'all 0.2s'
              }}
            >
              <div style={{
                color: currentSessionId === session.id ? '#60a5fa' : '#e2e8f0',
                fontWeight: '500',
                fontSize: '0.875rem',
                marginBottom: '0.25rem',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap'
              }}>
                {session.name}
              </div>
              <div style={{
                color: '#64748b',
                fontSize: '0.75rem',
                marginBottom: '0.25rem',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap'
              }}>
                {session.query}
              </div>
              <div style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                marginTop: '0.5rem'
              }}>
                <span style={{ color: '#94a3b8', fontSize: '0.75rem' }}>
                  {session.paper_count || 0} papers
                </span>
                <span style={{ color: '#64748b', fontSize: '0.75rem' }}>
                  {formatRelativeTime(session.created_at)}
                </span>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

export default SessionSidebar
