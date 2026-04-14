const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

async function fetchJSON(url, options = {}) {
  const response = await fetch(`${API_BASE}${url}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers
    }
  })
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }))
    throw new Error(error.detail || `HTTP ${response.status}`)
  }
  return response.json()
}

export const api = {
  health: () => fetchJSON('/health'),

  createSession: (name, query) => 
    fetchJSON('/sessions', {
      method: 'POST',
      body: JSON.stringify({ name, query })
    }),

  getSessions: () => fetchJSON('/sessions'),

  getSession: (sessionId) => fetchJSON(`/sessions/${sessionId}`),

  orchestrate: (sessionId, page = 0) =>
    fetchJSON(`/sessions/${sessionId}/orchestrate?page=${page}`, { method: 'POST' }),

  updateNote: (paperId, content) =>
    fetchJSON(`/papers/${paperId}/note`, {
      method: 'PATCH',
      body: JSON.stringify({ content })
    }),

  synthesize: (sessionId, paperIds) =>
    fetchJSON(`/sessions/${sessionId}/synthesize`, {
      method: 'POST',
      body: JSON.stringify(paperIds)
    }),

  exportBib: (sessionId) => `${API_BASE}/sessions/${sessionId}/export/bib`,

  exportTxt: (sessionId) => `${API_BASE}/sessions/${sessionId}/export/txt`,

  getConflicts: (sessionId) => fetchJSON(`/sessions/${sessionId}/conflicts`),

  resolveConflict: (sessionId, conflictId, resolutionNotes) =>
    fetchJSON(`/sessions/${sessionId}/conflicts/${conflictId}/resolve`, {
      method: 'POST',
      body: JSON.stringify({ resolution_notes: resolutionNotes })
    }),

  detectConflicts: (sessionId) =>
    fetchJSON(`/sessions/${sessionId}/detect-conflicts`, { method: 'POST' }),

  createDigest: (name, query, frequency, notifyEmail) =>
    fetchJSON('/digests', {
      method: 'POST',
      body: JSON.stringify({ name, query, frequency, notify_email: notifyEmail })
    }),

  getDigests: () => fetchJSON('/digests'),

  getDigest: (digestId) => fetchJSON(`/digests/${digestId}`),

  deleteDigest: (digestId) =>
    fetchJSON(`/digests/${digestId}`, { method: 'DELETE' }),

  toggleDigest: (digestId) =>
    fetchJSON(`/digests/${digestId}/toggle`, { method: 'PATCH' }),

  triggerDigestRun: (digestId) =>
    fetchJSON(`/digests/${digestId}/run`, { method: 'POST' }),

  previewDigest: (digestId) => fetchJSON(`/digests/${digestId}/preview`),

  generateRoadmap: (sessionId) =>
    fetchJSON(`/sessions/${sessionId}/roadmap`, { method: 'POST' }),

  getRoadmap: (sessionId) => fetchJSON(`/sessions/${sessionId}/roadmap`),

  executeRoadmapQuery: (sessionId, query) =>
    fetchJSON(
      `/sessions/${sessionId}/roadmap/query?query=${encodeURIComponent(query)}`,
      { method: 'POST' }
    )
}
