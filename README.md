# Orchestrix - Multi-Agent Research Intelligence Platform

Orchestrix is a full-stack web application that eliminates fragmentation in the academic research workflow through multi-agent AI orchestration. It queries multiple academic databases, performs analysis, generates citations, provides synthesis capabilities, detects conflicts between agent outputs, and supports scheduled research digests.

## Prerequisites

- Python 3.11+
- Node.js 18+
- npm or yarn

## Setup

### 1. Clone the Repository

```bash
git clone <repository-url>
cd Evolve-Hackathon
```

### 2. Backend Setup

```bash
cd backend

# Create virtual environment (recommended)
python3.12 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file and add your API key
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY

# The application will automatically create the SQLite database on first run
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

## Architecture

### Backend (Python FastAPI)

```
backend/
├── main.py              # FastAPI entrypoint and REST endpoints
├── orchestrator.py      # Central coordination layer
├── scheduler.py         # Background task scheduler for digests
├── models.py            # SQLAlchemy database models
├── database.py          # Database session management
├── schemas.py           # Pydantic request/response models
├── requirements.txt     # Python dependencies
├── .env.example         # Environment variables template
└── agents/
    ├── discovery.py      # Research Discovery Agent
    ├── analysis.py       # Analysis Agent
    ├── citation.py       # Citation Generator Agent
    ├── summarizer.py     # Summarization Agent
    ├── conflict_detector.py  # Conflict Detection Agent
    └── digest_scheduler.py   # Scheduled Digest Agent
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

Papers are ranked using a weighted combination of three factors:

```
score = 0.5 × normalize(citation_count) + 0.3 × normalize(year) + 0.2 × keyword_match_ratio
```

Where:
- **normalize(citation_count)**: Scales citations between 0-1 relative to the min/max in the result set
- **normalize(year)**: Scales year between 0-1 relative to min/max (with min=1990)
- **keyword_match_ratio**: Counts query words appearing in title+abstract, divided by total query words (stopwords removed)

## Safety Score Algorithm

The Safety Score feature is not applicable to this application as it focuses on academic research discovery rather than content safety assessment.

## Multi-Agent Pipeline

### Agent 1: Discovery Agent
Queries Semantic Scholar and arXiv APIs in parallel, normalizes results, deduplicates by title similarity, and computes relevance scores.

### Agent 2: Analysis Agent
Generates five types of analysis:
- **Publication Trend**: Papers per year
- **Top Authors**: Top 15 authors by frequency
- **Keyword Frequency**: Top 40 keywords from abstracts
- **Citation Distribution**: Histogram buckets (0, 1-10, 11-50, 51-200, 201-1000, 1000+)
- **Emerging Topics**: Words with highest delta between recent (2020+) and historical frequency

### Agent 3: Citation Generator Agent
Uses Gemini API to generate properly formatted citations in APA, MLA, IEEE, and Chicago styles.

### Agent 4: Summarization Agent
Two functions:
- **summarize_paper**: Generates structured summary with abstract compression, key contributions, methodology, and limitations
- **synthesize_papers**: Combines multiple papers into a cohesive paragraph identifying common themes, contradictions, and research gaps

### Agent 5: Conflict Detection Agent
Detects contradictions between Analysis and Summarization agents:
- **Semantic Contradiction**: Analysis keywords vs summary content
- **Methodology Mismatch**: Analysis focus vs paper methodology
- **Temporal Contradiction**: Emerging topics vs historical references
- **Citation Impact Contradiction**: High citations vs perceived limitations
- **Author Dominance Contradiction**: Few authors dominate vs underemphasized contributions
- **Keyword Mismatch**: Analysis keywords vs summary emphasis

### Agent 6: Digest Scheduler Agent
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
| POST | /sessions/{id}/orchestrate | Run orchestration pipeline |
| PATCH | /papers/{id}/note | Update paper note |
| POST | /sessions/{id}/synthesize | Synthesize selected papers |
| GET | /sessions/{id}/export/bib | Export as BibTeX |
| GET | /sessions/{id}/export/txt | Export citations as text |

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

### Google Gemini API
- **Purpose**: AI-powered citation formatting and summarization
- **Documentation**: https://ai.google.dev/docs
- **Requirements**: API key in .env file

## Environment Variables

### Backend (.env)
```
GEMINI_API_KEY=your_gemini_api_key_here
DATABASE_URL=sqlite:///./orchestrix.db
FRONTEND_URL=http://localhost:5173
```

### Frontend (.env)
```
VITE_API_BASE_URL=http://localhost:8000
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
