import type {
  TokenResponse,
  Session,
  SessionFull,
  OrchestrateResponse,
  NoteResponse,
  ConflictResponse,
  ConflictDetectionResult,
  ScheduledDigest,
  ScheduledDigestWithRuns,
  HealthResponse,
  RoadmapResponse,
  User,
} from './types/api';
import { supabase } from './lib/supabase';

const API_BASE: string = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
const TOKEN_KEY = 'orchestrix_token';
const USER_KEY = 'orchestrix_user';

export async function getToken(): Promise<string | null> {
  const { data: { session } } = await supabase.auth.getSession();
  if (session?.access_token) {
    return session.access_token;
  }
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function removeToken(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

export function getUser(): User | null {
  const userStr = localStorage.getItem(USER_KEY);
  return userStr ? (JSON.parse(userStr) as User) : null;
}

export function setUser(user: User): void {
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function isAuthenticated(): boolean {
  return !!getToken();
}

async function fetchJSON<T>(url: string, options: RequestInit = {}): Promise<T> {
  const token = await getToken();

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> || {}),
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE}${url}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    if (response.status === 401) {
      removeToken();
      window.dispatchEvent(new CustomEvent('auth:logout'));
    }
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error((error as { detail: string }).detail || `HTTP ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  health: (): Promise<HealthResponse> => fetchJSON<HealthResponse>('/health'),

  register: async (
    email: string,
    username: string,
    password: string,
    confirmPassword: string,
  ): Promise<TokenResponse> => {
    const data = await fetchJSON<TokenResponse>('/auth/register', {
      method: 'POST',
      body: JSON.stringify({ email, username, password, confirm_password: confirmPassword }),
    });

    if (data.access_token) {
      setToken(data.access_token);
      setUser(data.user);
    }
    return data;
  },

  login: async (email: string, password: string): Promise<TokenResponse> => {
    const data = await fetchJSON<TokenResponse>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });

    if (data.access_token) {
      setToken(data.access_token);
      setUser(data.user);
    }
    return data;
  },

  logout: async (): Promise<void> => {
    try {
      await fetchJSON<{ message: string }>('/auth/logout', { method: 'POST' });
    } catch {
      // Ignore errors
    }
    removeToken();
    await supabase.auth.signOut();
    window.dispatchEvent(new CustomEvent('auth:logout'));
  },

  getCurrentUser: (): Promise<User> => fetchJSON<User>('/auth/me'),

  updateProfile: (data: Partial<User>): Promise<User> =>
    fetchJSON<User>('/auth/me', {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),

  createSession: (name: string, query: string): Promise<Session> =>
    fetchJSON<Session>('/sessions', {
      method: 'POST',
      body: JSON.stringify({ name, query }),
    }),

  getSessions: (): Promise<Session[]> => fetchJSON<Session[]>('/sessions'),

  getSession: (sessionId: string): Promise<SessionFull> =>
    fetchJSON<SessionFull>(`/sessions/${sessionId}`),

  orchestrate: (sessionId: string, page = 0): Promise<OrchestrateResponse> =>
    fetchJSON<OrchestrateResponse>(`/sessions/${sessionId}/orchestrate?page=${page}`, {
      method: 'POST',
    }),

  updateNote: (paperId: string, content: string): Promise<NoteResponse> =>
    fetchJSON<NoteResponse>(`/papers/${paperId}/note`, {
      method: 'PATCH',
      body: JSON.stringify({ content }),
    }),

  synthesize: (sessionId: string, paperIds: string[]): Promise<{ synthesis: string }> =>
    fetchJSON<{ synthesis: string }>(`/sessions/${sessionId}/synthesize`, {
      method: 'POST',
      body: JSON.stringify(paperIds),
    }),

  exportBib: (sessionId: string): string => {
    const token = localStorage.getItem(TOKEN_KEY);
    return `${API_BASE}/sessions/${sessionId}/export/bib${token ? `?token=${token}` : ''}`;
  },

  exportTxt: (sessionId: string): string => {
    const token = localStorage.getItem(TOKEN_KEY);
    return `${API_BASE}/sessions/${sessionId}/export/txt${token ? `?token=${token}` : ''}`;
  },

  getConflicts: (sessionId: string): Promise<ConflictResponse[]> =>
    fetchJSON<ConflictResponse[]>(`/sessions/${sessionId}/conflicts`),

  resolveConflict: (
    sessionId: string,
    conflictId: string,
    resolutionNotes: string,
  ): Promise<{ status: string; conflict_id: string }> =>
    fetchJSON<{ status: string; conflict_id: string }>(
      `/sessions/${sessionId}/conflicts/${conflictId}/resolve`,
      {
        method: 'POST',
        body: JSON.stringify({ resolution_notes: resolutionNotes }),
      },
    ),

  detectConflicts: (sessionId: string): Promise<ConflictDetectionResult> =>
    fetchJSON<ConflictDetectionResult>(`/sessions/${sessionId}/detect-conflicts`, {
      method: 'POST',
    }),

  createDigest: (
    name: string,
    query: string,
    frequency: string,
    notifyEmail: string | null,
  ): Promise<ScheduledDigest> =>
    fetchJSON<ScheduledDigest>('/digests', {
      method: 'POST',
      body: JSON.stringify({ name, query, frequency, notify_email: notifyEmail }),
    }),

  getDigests: (): Promise<ScheduledDigest[]> => fetchJSON<ScheduledDigest[]>('/digests'),

  getDigest: (digestId: string): Promise<ScheduledDigestWithRuns> =>
    fetchJSON<ScheduledDigestWithRuns>(`/digests/${digestId}`),

  deleteDigest: (digestId: string): Promise<void> =>
    fetchJSON<void>(`/digests/${digestId}`, { method: 'DELETE' }),

  toggleDigest: (digestId: string): Promise<ScheduledDigest> =>
    fetchJSON<ScheduledDigest>(`/digests/${digestId}/toggle`, { method: 'PATCH' }),

  triggerDigestRun: (digestId: string): Promise<void> =>
    fetchJSON<void>(`/digests/${digestId}/run`, { method: 'POST' }),

  previewDigest: (digestId: string): Promise<{ new_papers_preview: unknown[] }> =>
    fetchJSON<{ new_papers_preview: unknown[] }>(`/digests/${digestId}/preview`),

  generateRoadmap: (sessionId: string): Promise<RoadmapResponse> =>
    fetchJSON<RoadmapResponse>(`/sessions/${sessionId}/roadmap`, { method: 'POST' }),

  getRoadmap: (sessionId: string): Promise<RoadmapResponse> =>
    fetchJSON<RoadmapResponse>(`/sessions/${sessionId}/roadmap`),

  executeRoadmapQuery: (
    sessionId: string,
    query: string,
  ): Promise<{ triggered_query: string; orchestration_result: OrchestrateResponse }> =>
    fetchJSON<{ triggered_query: string; orchestration_result: OrchestrateResponse }>(
      `/sessions/${sessionId}/roadmap/query?query=${encodeURIComponent(query)}`,
      { method: 'POST' },
    ),
};
