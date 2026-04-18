const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

const TOKEN_KEY = 'orchestrix_token'
const USER_KEY = 'orchestrix_user'

// Import Supabase client for auth methods
import { supabase } from './lib/supabase'

export function getToken() {
  // First try to get from Supabase session
  const supabaseSession = supabase.auth.getSession()
  if (supabaseSession.data?.session?.access_token) {
    return supabaseSession.data.session.access_token
  }
  // Fallback to localStorage
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token) {
  // Supabase manages tokens internally, this is for fallback
  localStorage.setItem(TOKEN_KEY, token)
}

export function removeToken() {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
}

export function getUser() {
  const userStr = localStorage.getItem(USER_KEY)
  return userStr ? JSON.parse(userStr) : null
}

export function setUser(user) {
  localStorage.setItem(USER_KEY, JSON.stringify(user))
}

export function isAuthenticated() {
  return !!getToken()
}

async function fetchJSON(url, options = {}) {
  const token = getToken()
  
  const headers = {
    'Content-Type': 'application/json',
    ...options.headers
  }
  
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  
  const response = await fetch(`${API_BASE}${url}`, {
    ...options,
    headers
  })
  
  if (!response.ok) {
    if (response.status === 401) {
      removeToken()
      window.dispatchEvent(new CustomEvent('auth:logout'))
    }
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }))
    throw new Error(error.detail || `HTTP ${response.status}`)
  }
  return response.json()
}

// Auth functions now use Supabase directly for registration/login
// But we still call the backend for other operations
export const api = {
  // Auth methods - use Supabase directly
  health: () => fetchJSON('/health'),

  register: async (email, username, password, confirmPassword) => {
    // Use backend endpoint which uses Supabase
    const data = await fetchJSON('/auth/register', {
      method: 'POST',
      body: JSON.stringify({ email, username, password, confirm_password: confirmPassword })
    })
    
    // Store token from Supabase response
    if (data.access_token) {
      setToken(data.access_token)
      setUser(data.user)
    }
    return data
  },

  login: async (email, password) => {
    // Use backend endpoint which uses Supabase
    const data = await fetchJSON('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password })
    })
    
    // Store token from Supabase response
    if (data.access_token) {
      setToken(data.access_token)
      setUser(data.user)
    }
    return data
  },

  logout: async () => {
    // Call backend logout endpoint
    try {
      await fetchJSON('/auth/logout', { method: 'POST' })
    } catch (e) {
      // Ignore errors
    }
    removeToken()
    // Also sign out from Supabase
    await supabase.auth.signOut()
    window.dispatchEvent(new CustomEvent('auth:logout'))
  },

  getCurrentUser: () => fetchJSON('/auth/me'),

  updateProfile: (data) => fetchJSON('/auth/me', {
    method: 'PATCH',
    body: JSON.stringify(data)
  }),

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

  exportBib: (sessionId) => {
    const token = getToken()
    return `${API_BASE}/sessions/${sessionId}/export/bib${token ? `?token=${token}` : ''}`
  },

  exportTxt: (sessionId) => {
    const token = getToken()
    return `${API_BASE}/sessions/${sessionId}/export/txt${token ? `?token=${token}` : ''}`
  },

  getConflicts: (sessionId) => fetchJSON(`/sessions/${sessionId}/conflicts`),

  resolveConflict: (sessionId, conflictId, resolutionNotes) =>
    fetchJSON(`/sessions/${session_id}/conflicts/${conflict_id}/resolve`, {
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