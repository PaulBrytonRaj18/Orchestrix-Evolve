// ── Auth Types ──

export interface User {
  id: string;
  email: string;
  username: string;
  is_active: boolean;
  is_admin: boolean;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token?: string;
  token_type: string;
  user: User;
}

// ── Session Types ──

export interface Session {
  id: string;
  user_id: string | null;
  name: string;
  query: string;
  created_at: string;
  updated_at: string;
  paper_count?: number;
}

export interface SessionFull extends Session {
  papers: PaperWithDetails[];
  analyses: AnalysisResponse[];
  syntheses: SynthesisResponse[];
  conflicts: ConflictResponse[];
}

export interface SessionCreate {
  name: string;
  query: string;
}

// ── Paper Types ──

export interface Paper {
  id: string;
  title: string;
  authors: string[];
  year: number | null;
  abstract: string | null;
  source_url: string | null;
  citation_count: number | null;
  relevance_score: number | null;
  external_id: string | null;
  source: string;
  citation?: CitationResponse | null;
  summary?: SummaryResponse | null;
  notes?: Note[];
  created_at: string;
  updated_at: string;
}

export interface PaperWithDetails extends Paper {
  session_id: string;
  summary: SummaryResponse | null;
  citation: CitationResponse | null;
  notes: NoteResponse[];
}

// ── Analysis Types ──

export interface AnalysisResponse {
  id: string;
  session_id: string;
  analysis_type: string;
  data_json: AnalysisData;
  created_at: string;
  updated_at: string;
}

export interface AnalysisData {
  publication_trend: PublicationTrend[];
  top_authors: TopAuthor[];
  keyword_frequency: KeywordFrequency[];
  citation_distribution: CitationDistribution[];
  emerging_topics: EmergingTopic[];
}

export interface PublicationTrend {
  year: number;
  count: number;
}

export interface TopAuthor {
  name: string;
  count: number;
}

export interface KeywordFrequency {
  word: string;
  count: number;
}

export interface CitationDistribution {
  bucket: string;
  count: number;
}

export interface EmergingTopic {
  word: string;
  delta: number;
  recent_count: number;
  historical_count: number;
}

// ── Summary Types ──

export interface SummaryResponse {
  id: string;
  paper_id: string;
  abstract_compression: string | null;
  key_contributions: string | null;
  methodology: string | null;
  limitations: string | null;
  created_at: string;
  updated_at: string;
}

// ── Synthesis Types ──

export interface SynthesisResponse {
  id: string;
  session_id: string;
  paper_ids: string[];
  content: string | null;
  created_at: string;
  updated_at: string;
}

// ── Citation Types ──

export interface CitationResponse {
  id: string;
  paper_id: string;
  apa: string | null;
  mla: string | null;
  ieee: string | null;
  chicago: string | null;
  created_at: string;
  updated_at: string;
}

export type CitationStyle = 'apa' | 'mla' | 'ieee' | 'chicago';

// ── Note Types ──

export interface Note {
  id: string;
  paper_id: string;
  content: string;
  created_at: string;
  updated_at: string;
}

export interface NoteCreate {
  content: string;
}

export interface NoteResponse {
  id: string;
  paper_id: string;
  content: string;
  created_at: string;
  updated_at: string;
}

// ── Conflict Types ──

export interface ConflictResponse {
  id: string;
  session_id: string;
  conflict_type: string;
  severity: 'high' | 'medium' | 'low';
  title: string;
  description: string | null;
  analysis_insight: string | null;
  summarization_insight: string | null;
  resolved: boolean;
  resolution_notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface ConflictResolve {
  resolution_notes: string;
}

export interface ConflictDetectionResult {
  conflicts: ConflictResponse[];
  summary: string;
}

// ── Digest Types ──

export interface ScheduledDigest {
  id: string;
  name: string;
  query: string;
  frequency: 'daily' | 'weekly' | 'biweekly' | 'monthly';
  last_run_at: string | null;
  next_run_at: string | null;
  is_active: boolean;
  notify_email: string | null;
  created_at: string;
  updated_at: string;
}

export interface ScheduledDigestCreate {
  name: string;
  query: string;
  frequency: string;
  notify_email?: string;
}

export interface DigestRunResponse {
  id: string;
  scheduled_digest_id: string;
  session_id: string | null;
  query: string;
  new_papers_count: number;
  new_paper_ids: string[];
  status: string;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface ScheduledDigestWithRuns extends ScheduledDigest {
  runs: DigestRunResponse[];
}

// ── Roadmap Types ──

export interface FoundationalPaper {
  paper_id: string;
  title: string;
  reason: string;
  citation_count: number;
  year: number;
  priority: number;
}

export interface GapArea {
  question: string;
  evidence: string;
  related_papers: string[];
  severity: string;
}

export interface NextQuery {
  query: string;
  rationale: string;
  trigger_action: string;
  expected_insight: string;
}

export interface RoadmapResponse {
  foundational_papers: FoundationalPaper[];
  gap_areas: GapArea[];
  next_query_suggestions: NextQuery[];
}

// ── Orchestration Types ──

export interface OrchestrateResponse {
  papers: PaperWithDetails[];
  analysis: AnalysisData | null;
  citations: Array<{ paper: PaperWithDetails; citation: CitationResponse }>;
  summaries: SummaryResponse[];
  trace: AgentTrace[];
  conflicts: ConflictResponse[];
  conflict_summary: string;
  roadmap: RoadmapResponse;
}

// ── Agent Trace Types ──

export interface AgentTrace {
  agent: string;
  status: 'running' | 'done' | 'error' | 'skipped';
  result?: string;
  reason?: string;
  error?: string;
  duration?: number;
  timestamp?: string;
}

// ── Health Types ──

export interface HealthResponse {
  status: string;
}

// ── API Error ──

export interface ApiError {
  detail: string;
}

// ── Generic Types ──

export type TabId = 'papers' | 'analysis' | 'citations' | 'summary' | 'conflicts' | 'roadmap';

export interface TabDefinition {
  id: TabId;
  label: string;
  icon: React.ElementType;
}
