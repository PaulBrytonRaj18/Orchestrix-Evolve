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
  SynthesisResponse,
  User,
  JobCreate,
  JobResponse,
  JobStatus,
  JobStreamHandlers,
  RelatedPapersResponse,
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

async function fetchBlob(url: string): Promise<Blob> {
  const token = await getToken();
  const headers: Record<string, string> = {};
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  const response = await fetch(`${API_BASE}${url}`, { headers });
  if (!response.ok) throw new Error(`Download failed: HTTP ${response.status}`);
  return response.blob();
}

function downloadBlob(blob: Blob, filename: string, _mimeType: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// ── Server-Sent Events over fetch ────────────────────────────────────────────
// EventSource cannot send an Authorization header, so the stream is read with
// fetch + ReadableStream. The server replays a snapshot on every connect, so a
// dropped connection is simply re-opened (bounded retries with backoff).

function parseSseBlock(block: string): { event: string; data: string } | null {
  let event = 'message';
  const data: string[] = [];
  for (const line of block.split('\n')) {
    if (line.startsWith(':')) continue; // keep-alive comment
    if (line.startsWith('event:')) event = line.slice(6).trim();
    else if (line.startsWith('data:')) data.push(line.slice(5).trimStart());
  }
  return data.length ? { event, data: data.join('\n') } : null;
}

const wait = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

async function streamJobOnce(
  jobId: string,
  handlers: JobStreamHandlers,
  signal: AbortSignal,
): Promise<'finished' | 'dropped'> {
  const token = await getToken();
  const response = await fetch(`${API_BASE}/jobs/${jobId}/events`, {
    headers: {
      Accept: 'text/event-stream',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    signal,
  });
  if (response.status === 401) {
    removeToken();
    window.dispatchEvent(new CustomEvent('auth:logout'));
    throw new Error('Session expired — please sign in again');
  }
  if (!response.ok || !response.body) {
    const body = await response.json().catch(() => ({ detail: `HTTP ${response.status}` }));
    throw new Error((body as { detail?: string }).detail || `HTTP ${response.status}`);
  }
  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = '';
  for (;;) {
    const { value, done } = await reader.read();
    if (done) return 'dropped';
    buffer += value.replace(/\r\n/g, '\n');
    let boundary = buffer.indexOf('\n\n');
    while (boundary !== -1) {
      const parsed = parseSseBlock(buffer.slice(0, boundary));
      buffer = buffer.slice(boundary + 2);
      boundary = buffer.indexOf('\n\n');
      if (!parsed) continue;
      const data = JSON.parse(parsed.data);
      switch (parsed.event) {
        case 'status':
          handlers.onStatus?.((data as { status: JobStatus }).status);
          break;
        case 'trace':
          handlers.onTrace?.(data);
          break;
        case 'papers':
          handlers.onPapers?.(data);
          break;
        case 'done':
          handlers.onDone(data);
          await reader.cancel();
          return 'finished';
        case 'error':
          handlers.onError((data as { message: string }).message);
          await reader.cancel();
          return 'finished';
      }
    }
  }
}

/** Follow a job until it finishes. Resolves when done/error was delivered or aborted. */
export async function streamJob(
  jobId: string,
  handlers: JobStreamHandlers,
  signal: AbortSignal,
  maxReconnects = 5,
): Promise<void> {
  for (let attempt = 0; ; attempt++) {
    try {
      if ((await streamJobOnce(jobId, handlers, signal)) === 'finished') return;
    } catch (error) {
      if (signal.aborted) return;
      if (attempt >= maxReconnects) {
        handlers.onError(error instanceof Error ? error.message : 'Lost connection to the server');
        return;
      }
    }
    if (signal.aborted) return;
    if (attempt >= maxReconnects) {
      handlers.onError('Lost connection to the server');
      return;
    }
    await wait(Math.min(500 * 2 ** attempt, 8000));
  }
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

  synthesize: (sessionId: string, paperIds: string[]): Promise<SynthesisResponse> =>
    fetchJSON<SynthesisResponse>(`/sessions/${sessionId}/synthesize`, {
      method: 'POST',
      body: JSON.stringify({ paper_ids: paperIds }),
    }),

  exportBib: async (sessionId: string): Promise<void> => {
    const blob = await fetchBlob(`/sessions/${sessionId}/export/bib`);
    downloadBlob(blob, `${sessionId}.bib`, 'application/x-bibtex');
  },

  exportTxt: async (sessionId: string): Promise<void> => {
    const blob = await fetchBlob(`/sessions/${sessionId}/export/txt`);
    downloadBlob(blob, `${sessionId}.txt`, 'text/plain');
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

  startJob: (sessionId: string, body: JobCreate = {}): Promise<JobResponse> =>
    fetchJSON<JobResponse>(`/sessions/${sessionId}/jobs`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  getRelated: (paperId: string, limit = 5): Promise<RelatedPapersResponse> =>
    fetchJSON<RelatedPapersResponse>(`/papers/${paperId}/related?limit=${limit}`),

  getJob: (jobId: string): Promise<JobResponse> => fetchJSON<JobResponse>(`/jobs/${jobId}`),

  listSessionJobs: (sessionId: string): Promise<JobResponse[]> =>
    fetchJSON<JobResponse[]>(`/sessions/${sessionId}/jobs`),

  executeRoadmapQuery: (
    sessionId: string,
    query: string,
  ): Promise<{ triggered_query: string; orchestration_result: OrchestrateResponse }> =>
    fetchJSON<{ triggered_query: string; orchestration_result: OrchestrateResponse }>(
      `/sessions/${sessionId}/roadmap/query?query=${encodeURIComponent(query)}`,
      { method: 'POST' },
    ),
};
