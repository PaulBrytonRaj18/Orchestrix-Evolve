# Orchestrix - Multi-Agent Research Intelligence Platform

Orchestrix is a full-stack web application that eliminates fragmentation in the academic research workflow through multi-agent AI orchestration. It queries multiple academic databases, performs analysis, generates citations, provides synthesis capabilities, detects conflicts between agent outputs, and supports scheduled research digests.

[![CI](https://github.com/Paul-Bryton-Raj/Orchestrix-Evolve/actions/workflows/ci.yml/badge.svg)](https://github.com/Paul-Bryton-Raj/Orchestrix-Evolve/actions/workflows/ci.yml)
[![Security Scan](https://github.com/Paul-Bryton-Raj/Orchestrix-Evolve/actions/workflows/security.yml/badge.svg)](https://github.com/Paul-Bryton-Raj/Orchestrix-Evolve/actions/workflows/security.yml)

## Prerequisites

- Python 3.12+ (3.12 and 3.13 tested)
- Node.js 18+
- npm or yarn

## Setup

### 1. Clone the Repository

```bash
git clone <repository-url>
cd Orchestrix-Evolve
```

### 2. Backend Setup

```bash
cd backend

# Create virtual environment (recommended)
python3.12 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies (requirements-dev.txt adds pytest, respx and ruff)
pip install -r requirements-dev.txt

# Configure: Supabase URL/service key, optional GROQ_API_KEY, SEMANTIC_SCHOLAR_API_KEY
cp .env.example .env

# Without SUPABASE_DB_URL / DATABASE_URL a local SQLite file is used and created on
# first run. For Postgres/Supabase apply migrations first:
alembic upgrade head
```

### 3. Frontend Setup

```bash
cd ../frontend

# Install dependencies
npm install

# Create environment file
echo "VITE_API_BASE_URL=http://localhost:8000" > .env
```

### 4. Running the Application

**Terminal 1 - Backend:**
```bash
cd backend
source venv/bin/activate
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Terminal 2 - Frontend:**
```bash
cd frontend
npm run dev
```

The application will be available at:
- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- API Documentation: http://localhost:8000/docs

### 5. Docker (optional)

```bash
docker build -t orchestrix-backend --target production backend/
docker run --env-file backend/.env -p 8000:8000 orchestrix-backend
```

The production image runs `alembic upgrade head` before starting uvicorn.

### 6. Tests

```bash
cd backend
pytest                                   # 190 tests, SQLite, no network
TEST_DATABASE_URL=postgresql://... pytest  # same suite against Postgres
RUN_LIVE=1 pytest -m live                # contract checks against the real APIs
ruff check . && ruff format --check .
```

## CI/CD

This project uses GitHub Actions for continuous integration and deployment:

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| PR Checks | Pull requests | Lint, typecheck, build, test |
| CI | Push to main/develop | Full pipeline + Docker build |
| Security Scan | Weekly + manual | Dependency audit, SAST, secrets scan |
| Deploy | Manual | Build & push Docker images to ghcr.io |

## Architecture

### Backend (Python FastAPI)

```
backend/
├── main.py              # App wiring: middleware, error handlers, /health, routers
├── config.py            # Typed settings (pydantic-settings) — the only env reader
├── database.py          # SQLAlchemy engine/session (SQLite or Postgres via psycopg 3)
├── models.py            # ORM models
├── schemas.py           # Pydantic v2 request/response models
├── auth.py              # Supabase JWT verification (JWKS or HS256) + Supabase clients
├── llm.py               # Shared Groq client: JSON mode, rate limiter, concurrency cap
├── rate_limit.py        # Auth endpoint rate limiting
├── orchestrator.py      # Agent dependency graph, concurrent stages, per-agent trace
├── scheduler.py         # APScheduler digest jobs
├── routers/             # auth.py, sessions.py, digests.py
├── services/
│   └── persistence.py   # Saves orchestration output; eager-loaded session views
├── agents/
│   ├── discovery.py         # Semantic Scholar + arXiv + OpenAlex, TF-IDF ranking
│   ├── analysis.py          # Trends, authors, keywords, citations, emerging topics
│   ├── citation.py          # APA 7 / MLA 9 / IEEE / Chicago formatting
│   ├── summarizer.py        # LLM summaries + synthesis (extractive fallback)
│   ├── conflict_detector.py # Analysis-vs-summary contradiction heuristics
│   ├── roadmap.py           # Foundational papers, gaps, next queries
│   └── digest_scheduler.py  # "New since last run" search for digests
├── alembic/             # Migrations (002 removes the user_id → users FKs)
└── tests/               # API, auth, agents, orchestrator, live-contract tests
```

### Frontend (React + Vite)

```
frontend/
├── package.json
├── vite.config.js
├── index.html
└── src/
    ├── main.jsx
    ├── App.jsx
    ├── api.js
    ├── pages/
    │   ├── Search.jsx
    │   ├── Dashboard.jsx
    │   └── SessionCompare.jsx
    └── components/
        ├── AgentTraceLog.jsx
        ├── PaperCard.jsx
        ├── AnalysisCharts.jsx
        ├── CitationPanel.jsx
        ├── SummaryPanel.jsx
        └── SessionSidebar.jsx
```

## Database Schema

### Sessions Table
| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| name | String | User-defined session name |
| query | String | Original search query |
| created_at | DateTime | UTC timestamp |
| updated_at | DateTime | Last update timestamp |

### Papers Table
| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| session_id | UUID | Foreign key to sessions |
| title | String | Paper title |
| authors | JSON | Array of author names |
| year | Integer | Publication year |
| abstract | Text | Paper abstract |
| source_url | String | URL to the paper |
| citation_count | Integer | Number of citations |
| relevance_score | Float | Computed relevance score |
| external_id | String | ID from source API |
| source | String | "semantic_scholar" or "arxiv" |

### Analyses Table
| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| session_id | UUID | Foreign key to sessions |
| analysis_type | String | One of: publication_trend, top_authors, keyword_frequency, citation_distribution, emerging_topics |
| data_json | JSON | Computed analysis results |

### Summaries Table
| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| paper_id | UUID | Foreign key to papers |
| abstract_compression | Text | Plain-language summary |
| key_contributions | Text | Main novel contributions |
| methodology | Text | Methods/approach description |
| limitations | Text | Known/inferred limitations |

### Citations Table
| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| paper_id | UUID | Foreign key to papers |
| apa | Text | APA format citation |
| mla | Text | MLA format citation |
| ieee | Text | IEEE format citation |
| chicago | Text | Chicago format citation |

### Notes Table
| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| paper_id | UUID | Foreign key to papers |
| content | Text | Free-text notes |

### Conflicts Table
| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| session_id | UUID | Foreign key to sessions |
| conflict_type | String | Type: semantic_contradiction, methodology_mismatch, temporal_contradiction, etc. |
| severity | String | high, medium, or low |
| title | String | Brief conflict title |
| description | Text | Detailed description |
| analysis_insight | Text | What the Analysis Agent found |
| summarization_insight | Text | What the Summarization Agent found |
| resolved | Boolean | Whether conflict is resolved |
| resolution_notes | Text | Notes on resolution |

### Scheduled Digests Table
| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| name | String | Digest name |
| query | String | Search query to run |
| frequency | String | daily, weekly, biweekly, or monthly |
| last_run_at | DateTime | When digest last ran |
| next_run_at | DateTime | When digest will next run |
| is_active | Boolean | Whether digest is active |
| notify_email | String | Email for notifications |

### Digest Runs Table
| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| scheduled_digest_id | UUID | Foreign key to scheduled_digests |
| session_id | UUID | Foreign key to sessions (created session) |
| query | String | Query that was run |
| new_papers_count | Integer | Number of new papers found |
| new_paper_ids | JSON | Array of new paper external IDs |
| status | String | pending, running, completed, or failed |
| error_message | Text | Error details if failed |

## Relevance Scoring Formula

After cross-source de-duplication (DOI, arXiv id, normalised title, title Jaccard ≥ 0.85),
each paper gets a score in [0, 1]:

```
score = 0.35 × tfidf_cosine(query, title+abstract)
      + 0.20 × fraction of query terms present
      + 0.25 × log(1 + citations) / log(1 + max_citations)
      + 0.10 × normalised publication year
      + 0.10 × venue tier
```

Citations are log-scaled because counts are heavy-tailed. Ranking runs in a worker thread.

## Safety Score Algorithm

The Safety Score feature is not applicable to this application as it focuses on academic research discovery rather than content safety assessment.

## Multi-Agent Pipeline

### Agent 1: Discovery Agent
Queries Semantic Scholar, arXiv and OpenAlex concurrently over one pooled HTTP client (bounded retries, `Retry-After` aware), normalises DOIs/arXiv ids, merges duplicates keeping the richest metadata, and ranks with the formula above. A failing source degrades the result set instead of failing the request.

### Agent 2: Analysis Agent
Generates five types of analysis:
- **Publication Trend**: Papers per year
- **Top Authors**: Top 15 authors by frequency
- **Keyword Frequency**: Top 40 keywords from abstracts
- **Citation Distribution**: Histogram buckets (0, 1-10, 11-50, 51-200, 201-1000, 1000+)
- **Emerging Topics**: Words with highest delta between the last three years and older papers

### Agent 3: Citation Generator Agent
Deterministic formatter for APA 7, MLA 9, IEEE and Chicago author-date (family-name/initials handling, et al. rules, DOI links). No LLM needed.

### Agent 4: Summarization Agent
Two functions:
- **summarize_paper**: Groq LLM in JSON mode → abstract compression, key contributions, methodology, limitations (linked to the paper by id). Falls back to an extractive summary when no key is set or the call fails
- **synthesize_papers**: Combines multiple papers into a cohesive paragraph identifying common themes, contradictions, and research gaps

### Agent 5: Conflict Detection Agent
Detects contradictions between Analysis and Summarization agents:
- **Semantic Contradiction**: Analysis keywords vs summary content
- **Methodology Mismatch**: Analysis focus vs paper methodology
- **Temporal Contradiction**: Emerging topics vs historical references
- **Citation Impact Contradiction**: High citations vs perceived limitations
- **Author Dominance Contradiction**: Few authors dominate vs underemphasized contributions
- **Keyword Mismatch**: Analysis keywords vs summary emphasis

### Agent 6: Roadmap Agent
Ranks foundational papers by citation impact and velocity, derives gap areas from analysis, summaries and open conflicts, and proposes up to five runnable follow-up queries anchored on the session topic.

### Agent 7: Digest Scheduler Agent
Manages scheduled research digests:
- Supports daily, weekly, biweekly, and monthly frequencies
- Tracks papers seen to identify truly new papers
- Generates email notifications for new findings
- Creates sessions for digest runs

## API Endpoints

### Core Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /health | Health check |
| POST | /sessions | Create new session |
| GET | /sessions | List all sessions |
| GET | /sessions/{id} | Get session with all data |
| DELETE | /sessions/{id} | Delete a session and its data |
| POST | /sessions/{id}/orchestrate | Run orchestration pipeline |
| PATCH | /papers/{id}/note | Update paper note |
| POST | /sessions/{id}/synthesize | Synthesize selected papers |
| GET | /sessions/{id}/export/bib | Export as BibTeX |
| GET | /sessions/{id}/export/txt?style=apa\|mla\|ieee\|chicago | Export citations as text |
| POST | /sessions/{id}/roadmap | Rebuild roadmap from stored data |
| GET | /sessions/{id}/roadmap | Get roadmap |
| POST | /sessions/{id}/roadmap/query?query=… | Run a suggested query into the session |

All endpoints except `/health` and `/auth/register|login|refresh` require `Authorization: Bearer <Supabase access token>`.

### Conflict Resolution Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /sessions/{id}/conflicts | Get all conflicts for a session |
| POST | /sessions/{id}/conflicts/{conflict_id}/resolve | Mark conflict as resolved |
| POST | /sessions/{id}/detect-conflicts | Run conflict detection on session |

### Scheduled Digest Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /digests | Create scheduled digest |
| GET | /digests | List all scheduled digests |
| GET | /digests/{id} | Get digest with run history |
| DELETE | /digests/{id} | Delete scheduled digest |
| PATCH | /digests/{id}/toggle | Enable/disable digest |
| POST | /digests/{id}/run | Manually trigger digest run |
| GET | /digests/{id}/preview | Preview new papers for digest |

## External APIs Used

### Semantic Scholar API
- **Purpose**: Academic paper search and metadata
- **Documentation**: https://api.semanticscholar.org/
- **Rate Limits**: Varies by tier

### arXiv API
- **Purpose**: Open-access preprint repository
- **Documentation**: https://arxiv.org/help/api
- **Rate Limits**: 1 request per 3 seconds

### OpenAlex API
- **Purpose**: Open scholarly metadata, citation counts, abstracts
- **Documentation**: https://docs.openalex.org/
- **Tip**: set `OPENALEX_MAILTO` to join the faster polite pool

### Groq API
- **Purpose**: LLM summaries, synthesis and (optional) LLM workflow planning
- **Documentation**: https://console.groq.com/docs
- **Optional**: without `GROQ_API_KEY` extractive summaries are used

Semantic Scholar's anonymous tier is heavily rate-limited on shared IPs; set
`SEMANTIC_SCHOLAR_API_KEY` in production.

## Environment Variables

See [`backend/.env.example`](backend/.env.example) for the full, commented list. Key ones:

| Variable | Purpose |
|----------|---------|
| `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` | Auth (JWT verification via JWKS, admin calls) |
| `SUPABASE_JWT_SECRET` | Only for legacy HS256-signed projects |
| `SUPABASE_DB_URL` / `DATABASE_URL` | Database; empty → local SQLite |
| `GROQ_API_KEY` | LLM summaries (optional) |
| `SEMANTIC_SCHOLAR_API_KEY`, `OPENALEX_MAILTO` | Better discovery rate limits |
| `ENABLE_SCHEDULER` | `true` on exactly one process |

### Frontend (.env)
```
VITE_API_BASE_URL=http://localhost:8000
VITE_SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co
VITE_SUPABASE_ANON_KEY=your-anon-key
```

## Features

### Search Page
- Prominent search bar for research queries
- Live agent activity trace with status indicators
- Four tabs: Papers, Analysis, Citations, Summary
- Paper cards with relevance score badges
- Interactive Recharts visualizations

### Dashboard Page
- Left sidebar with past sessions
- Full session details with all data
- Auto-saving notes with debounced updates
- Tab-based navigation

### Compare Page
- Side-by-side session selection
- Merged publication trend charts
- Unique keyword highlighting
- Paper overlap detection

### Conflict Resolution
- Automatic conflict detection during orchestration
- Manual conflict detection for existing sessions
- Conflict categorization by type and severity
- Resolution tracking with notes

### Scheduled Research Digests
- Create recurring queries with customizable frequency
- Automatic detection of new papers
- Email notifications for new findings
- Historical run tracking and statistics

## License

MIT License
