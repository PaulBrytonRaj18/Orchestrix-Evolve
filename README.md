# Orchestrix - Multi-Agent Research Intelligence Platform

Orchestrix is a full-stack web application that eliminates fragmentation in the academic research workflow through multi-agent AI orchestration. It queries multiple academic databases, performs analysis, generates citations, and provides synthesis capabilities.

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
python -m venv venv
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
├── orchestrator.py       # Central coordination layer
├── models.py             # SQLAlchemy database models
├── database.py           # Database session management
├── schemas.py            # Pydantic request/response models
├── requirements.txt      # Python dependencies
├── .env.example          # Environment variables template
└── agents/
    ├── discovery.py      # Research Discovery Agent
    ├── analysis.py      # Analysis Agent
    ├── citation.py      # Citation Generator Agent
    └── summarizer.py    # Summarization Agent
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

## API Endpoints

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

## License

MIT License
