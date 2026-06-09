import logging
import os
import threading
import time
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from agents import conflict_detector, digest_scheduler, summarizer
from auth import (
    get_current_user,
    get_supabase_client,
)
from database import close_engine, get_db, init_db, is_postgres
from models import (
    Analysis,
    Citation,
    Conflict,
    DigestRun,
    Note,
    Paper,
    Roadmap,
    ScheduledDigest,
    Summary,
    Synthesis,
)
from models import (
    Session as SessionModel,
)
from orchestrator import orchestrate
from scheduler import scheduler
from schemas import (
    AnalysisResponse,
    CitationResponse,
    ConflictDetectionResult,
    ConflictResolve,
    ConflictResponse,
    DigestRunResponse,
    HealthResponse,
    NoteCreate,
    NoteResponse,
    OrchestrateResponse,
    PaperWithDetails,
    RefreshTokenRequest,
    RoadmapResponse,
    ScheduledDigestCreate,
    ScheduledDigestResponse,
    ScheduledDigestWithRuns,
    SessionCreate,
    SessionFullResponse,
    SessionResponse,
    SummaryResponse,
    SynthesisResponse,
    TokenResponse,
    UserCreate,
    UserLogin,
    UserResponse,
    UserUpdate,
)

load_dotenv()

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

START_TIME = time.time()


def _validate_environment():
    errors = []
    required_vars = {
        "SUPABASE_URL": os.getenv("SUPABASE_URL"),
        "SUPABASE_SERVICE_KEY": os.getenv("SUPABASE_SERVICE_KEY"),
        "GROQ_API_KEY": os.getenv("GROQ_API_KEY"),
    }
    for name, value in required_vars.items():
        if not value:
            errors.append(f"{name} is not set")
    for name, value in required_vars.items():
        if value and value in (
            "your-secret-key-here-change-in-production",
            "change-me",
            "default",
            "your-groq-api-key",
            "your-supabase-service-role-key",
        ):
            errors.append(f"{name} is set to a known default value - change it for production")
    return errors


_app_startup_errors = _validate_environment()

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
CORS_ORIGINS_STR = os.getenv("CORS_ORIGINS", "")
if CORS_ORIGINS_STR:
    CORS_ORIGINS = [o.strip() for o in CORS_ORIGINS_STR.split(",")]
else:
    CORS_ORIGINS = [
        FRONTEND_URL,
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:3000",
    ]

_request_id_store: dict[str, list[float]] = {}
_rate_limit_store: dict[str, list[float]] = {}
_rate_limit_lock = threading.Lock()


def _rate_limit(key: str, max_requests: int = 20, window_seconds: int = 60) -> tuple[int, int]:
    now = time.time()
    with _rate_limit_lock:
        timestamps = _rate_limit_store.get(key, [])
        timestamps = [t for t in timestamps if now - t < window_seconds]
        if len(timestamps) >= max_requests:
            raise HTTPException(
                status_code=429,
                detail="Too many requests. Please try again later.",
                headers={
                    "X-RateLimit-Limit": str(max_requests),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(now + window_seconds)),
                    "Retry-After": str(window_seconds),
                },
            )
        timestamps.append(now)
        _rate_limit_store[key] = timestamps
    _prune_stale_rate_limit_keys()


def _prune_stale_rate_limit_keys():
    cutoff = time.time() - 3600
    stale = [k for k, v in _rate_limit_store.items() if v and v[-1] < cutoff]
    for k in stale:
        _rate_limit_store.pop(k, None)


app = FastAPI(title="Orchestrix API", version="2.0.0")


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
    return response


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration_ms = int((time.time() - start) * 1000)
    logger.info(
        f"{request.method} {request.url.path} {response.status_code} {duration_ms}ms"
        f" [{request.headers.get('X-Request-ID', '-')}]"
    )
    return response


app.add_middleware(GZipMiddleware, minimum_size=1000)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods="*",
    allow_headers="*",
    expose_headers=["Content-Disposition", "X-Request-ID"],
    max_age=600,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if _app_startup_errors:
        for err in _app_startup_errors:
            logger.error(f"Startup configuration error: {err}")
    init_db()
    if is_postgres():
        logger.info("Using PostgreSQL database")
    else:
        logger.info("Using SQLite database")
    scheduler.start()
    logger.info("Digest scheduler started")
    yield
    scheduler.stop()
    close_engine()
    logger.info("Application shutdown complete")


app.router.lifespan_context = lifespan


class AppError(Exception):
    def __init__(self, status_code: int, message: str, details: dict | None = None):
        self.status_code = status_code
        self.message = message
        self.details = details or {}


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message, "details": exc.details},
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    headers = dict(exc.headers or {})
    headers["X-Request-ID"] = request.headers.get("X-Request-ID", "")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=headers,
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    request_id = request.headers.get("X-Request-ID", "unknown")
    logger.error(f"Unhandled exception [req={request_id}]: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "request_id": request_id,
        },
    )


def _get_resource_or_404(
    model: type[Any],
    resource_id: str,
    db: Session,
    resource_name: str = "Resource",
    current_user_id: str | None = None,
) -> Any:
    resource = db.query(model).filter(model.id == resource_id).first()
    if not resource:
        raise HTTPException(status_code=404, detail=f"{resource_name} not found")
    if (
        current_user_id is not None
        and hasattr(resource, "user_id")
        and resource.user_id is not None
        and resource.user_id != current_user_id
    ):
        raise HTTPException(status_code=403, detail="Access denied")
    return resource


def _get_session_or_404(
    session_id: str, db: Session, current_user_id: str | None = None
) -> SessionModel:
    return _get_resource_or_404(
        SessionModel, session_id, db, "Session", current_user_id
    )


def _get_digest_or_404(
    digest_id: str, db: Session, current_user_id: str | None = None
) -> ScheduledDigest:
    return _get_resource_or_404(
        ScheduledDigest, digest_id, db, "Digest", current_user_id
    )


@app.get("/health", response_model=HealthResponse, tags=["Health"])
def health_check():
    db_status = "unknown"
    try:
        db = next(get_db())
        db.execute(text("SELECT 1"))
        db_status = "ok"
        db.close()
    except Exception:
        db_status = "error"

    return {
        "status": "ok" if db_status == "ok" else "degraded",
        "version": "2.0.0",
        "database": db_status,
        "uptime_seconds": time.time() - START_TIME,
    }


# ─── Auth ───────────────────────────────────────────────────────────────────

@app.post(
    "/auth/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Auth"],
)
def register(user_data: UserCreate, request: Request):
    _rate_limit(f"register:{request.client.host}", max_requests=5, window_seconds=300)
    try:
        supabase = get_supabase_client()
        response = supabase.auth.sign_up({
            "email": user_data.email,
            "password": user_data.password,
            "options": {"data": {"username": user_data.username}},
        })
        if response.user is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=response.data.get("message", "Registration failed"),
            )
        return {
            "access_token": response.session.access_token if response.session else "",
            "refresh_token": response.session.refresh_token if response.session else "",
            "token_type": "bearer",
            "user": {
                "id": response.user.id,
                "email": response.user.email,
                "username": response.user.user_metadata.get("username", ""),
                "is_active": True,
                "is_admin": False,
                "created_at": response.user.created_at,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Registration failed. Please check your information and try again.",
        )


@app.post("/auth/login", response_model=TokenResponse, tags=["Auth"])
def login(user_data: UserLogin, request: Request):
    _rate_limit(f"login:{request.client.host}", max_requests=10, window_seconds=300)
    try:
        supabase = get_supabase_client()
        response = supabase.auth.sign_in_with_password(
            {"email": user_data.email, "password": user_data.password}
        )
        if response.user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password"
            )
        return {
            "access_token": response.session.access_token,
            "refresh_token": response.session.refresh_token,
            "token_type": "bearer",
            "user": {
                "id": response.user.id,
                "email": response.user.email,
                "username": response.user.user_metadata.get("username", ""),
                "is_active": True,
                "is_admin": False,
                "created_at": response.user.created_at,
            },
        }
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password"
        )


@app.post("/auth/logout", tags=["Auth"])
def logout(current_user_id: str = Depends(get_current_user)):
    try:
        supabase = get_supabase_client()
        supabase.auth.sign_out()
        return {"message": "Successfully logged out"}
    except Exception as e:
        logger.error(f"Logout error: {str(e)}")
        return {"message": "Logged out (token may be invalid)"}


@app.get("/auth/me", response_model=UserResponse, tags=["Auth"])
def get_current_user_info(current_user_id: str = Depends(get_current_user)):
    try:
        supabase = get_supabase_client()
        response = supabase.auth.get_user()
        if not response.user:
            raise HTTPException(status_code=404, detail="User not found")
        return UserResponse(
            id=response.user.id,
            email=response.user.email,
            username=response.user.user_metadata.get("username", ""),
            is_active=True,
            is_admin=False,
            created_at=response.user.created_at,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get user error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get user info")


@app.post("/auth/refresh", response_model=TokenResponse, tags=["Auth"])
def refresh_token(refresh_data: RefreshTokenRequest, request: Request):
    _rate_limit(f"refresh:{request.client.host}", max_requests=10, window_seconds=300)
    try:
        supabase = get_supabase_client()
        response = supabase.auth.refresh_session(refresh_data.refresh_token)
        if not response.session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
            )
        return {
            "access_token": response.session.access_token,
            "refresh_token": response.session.refresh_token,
            "token_type": "bearer",
            "user": {
                "id": response.user.id if response.user else "",
                "email": response.user.email if response.user else "",
                "username": response.user.user_metadata.get("username", "")
                if response.user
                else "",
                "is_active": True,
                "is_admin": False,
                "created_at": response.user.created_at if response.user else datetime.now(UTC),
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token refresh error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Failed to refresh token"
        )


@app.patch("/auth/me", response_model=UserResponse, tags=["Auth"])
def update_current_user(user_update: UserUpdate, current_user_id: str = Depends(get_current_user)):
    try:
        supabase = get_supabase_client()
        attrs = {}
        if user_update.email is not None:
            attrs["email"] = user_update.email
        if user_update.password is not None:
            attrs["password"] = user_update.password
        if user_update.username is not None:
            attrs["data"] = {"username": user_update.username}
        if attrs:
            supabase.auth.update_user(attrs)
        response = supabase.auth.get_user()
        if not response.user:
            raise HTTPException(status_code=404, detail="User not found")
        return UserResponse(
            id=response.user.id,
            email=response.user.email,
            username=response.user.user_metadata.get("username", ""),
            is_active=True,
            is_admin=False,
            created_at=response.user.created_at,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update user error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update user")


# ─── Sessions ────────────────────────────────────────────────────────────────

@app.post(
    "/sessions",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Sessions"],
)
def create_session(
    session_data: SessionCreate,
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user),
):
    db_session = SessionModel(
        name=session_data.name,
        query=session_data.query,
        user_id=current_user_id,
    )
    db.add(db_session)
    db.commit()
    db.refresh(db_session)
    return SessionResponse(
        id=db_session.id,
        user_id=db_session.user_id,
        name=db_session.name,
        query=db_session.query,
        created_at=db_session.created_at,
        updated_at=db_session.updated_at,
        paper_count=0,
    )


@app.get("/sessions", response_model=list[SessionResponse], tags=["Sessions"])
def list_sessions(db: Session = Depends(get_db), current_user_id: str = Depends(get_current_user)):
    sessions = (
        db.query(SessionModel)
        .filter(SessionModel.user_id == current_user_id)
        .order_by(SessionModel.updated_at.desc())
        .all()
    )
    result = []
    for s in sessions:
        paper_count = db.query(Paper).filter(Paper.session_id == s.id).count()
        result.append(SessionResponse(
            id=s.id,
            user_id=s.user_id,
            name=s.name,
            query=s.query,
            created_at=s.created_at,
            updated_at=s.updated_at,
            paper_count=paper_count,
        ))
    return result


@app.get(
    "/sessions/{session_id}",
    response_model=SessionFullResponse,
    tags=["Sessions"],
)
def get_session(
    session_id: str,
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user),
):
    db_session = _get_session_or_404(session_id, db, current_user_id)
    papers = db.query(Paper).filter(Paper.session_id == session_id).all()
    analyses = db.query(Analysis).filter(Analysis.session_id == session_id).all()
    syntheses = db.query(Synthesis).filter(Synthesis.session_id == session_id).all()
    conflicts = db.query(Conflict).filter(Conflict.session_id == session_id).all()

    paper_details = []
    for p in papers:
        summary = db.query(Summary).filter(Summary.paper_id == p.id).first()
        citation = db.query(Citation).filter(Citation.paper_id == p.id).first()
        notes = db.query(Note).filter(Note.paper_id == p.id).all()
        paper_details.append(PaperWithDetails(
            id=p.id,
            session_id=p.session_id,
            title=p.title,
            authors=p.authors or [],
            year=p.year,
            abstract=p.abstract,
            source_url=p.source_url,
            citation_count=p.citation_count,
            relevance_score=p.relevance_score,
            external_id=p.external_id,
            source=p.source,
            created_at=p.created_at,
            updated_at=p.updated_at,
            summary=SummaryResponse.model_validate(summary) if summary else None,
            citation=CitationResponse.model_validate(citation) if citation else None,
            notes=[NoteResponse.model_validate(n) for n in notes],
        ))

    return SessionFullResponse(
        id=db_session.id,
        user_id=db_session.user_id,
        name=db_session.name,
        query=db_session.query,
        created_at=db_session.created_at,
        updated_at=db_session.updated_at,
        papers=paper_details,
        analyses=[AnalysisResponse.model_validate(a) for a in analyses],
        syntheses=[SynthesisResponse.model_validate(s) for s in syntheses],
        conflicts=[ConflictResponse.model_validate(c) for c in conflicts],
    )


@app.post(
    "/sessions/{session_id}/orchestrate",
    response_model=OrchestrateResponse,
    tags=["Sessions", "Orchestration"],
)
async def orchestrate_session(
    session_id: str,
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user),
):
    db_session = _get_session_or_404(session_id, db, current_user_id)
    try:
        result = await orchestrate(db_session.query, session_id)

        papers_data = result.get("papers", [])
        analysis_data = result.get("analysis")
        citations_data = result.get("citations", [])
        summaries_data = result.get("summaries", [])
        trace_data = result.get("trace", [])
        conflicts_data = result.get("conflicts", [])
        roadmap_data = result.get("roadmap")

        for paper_data in papers_data:
            existing = db.query(Paper).filter(
                Paper.session_id == session_id,
                Paper.external_id == paper_data.get("external_id"),
            ).first()
            if existing:
                continue
            paper = Paper(
                session_id=session_id,
                title=paper_data.get("title", ""),
                authors=paper_data.get("authors", []),
                year=paper_data.get("year"),
                abstract=paper_data.get("abstract"),
                source_url=paper_data.get("source_url"),
                citation_count=paper_data.get("citation_count"),
                relevance_score=paper_data.get("relevance_score"),
                external_id=paper_data.get("external_id"),
                source=paper_data.get("source", "unknown"),
            )
            db.add(paper)
            db.flush()

            paper_citation = paper_data.get("citation")
            if paper_citation:
                db.add(Citation(
                    paper_id=paper.id,
                    apa=paper_citation.get("apa"),
                    mla=paper_citation.get("mla"),
                    ieee=paper_citation.get("ieee"),
                    chicago=paper_citation.get("chicago"),
                ))

        if analysis_data:
            db.add(Analysis(
                session_id=session_id,
                analysis_type="full",
                data_json=analysis_data,
            ))

        for summary_data in summaries_data:
            paper_id = summary_data.get("paper_id")
            if paper_id:
                existing_summary = db.query(Summary).filter(Summary.paper_id == paper_id).first()
                if not existing_summary:
                    db.add(Summary(
                        paper_id=paper_id,
                        abstract_compression=summary_data.get("abstract_compression"),
                        key_contributions=summary_data.get("key_contributions"),
                        methodology=summary_data.get("methodology"),
                        limitations=summary_data.get("limitations"),
                    ))

        for conflict_data in conflicts_data:
            db.add(Conflict(
                session_id=session_id,
                conflict_type=conflict_data.get("conflict_type", "unknown"),
                severity=conflict_data.get("severity", "medium"),
                title=conflict_data.get("title", ""),
                description=conflict_data.get("description"),
                analysis_insight=conflict_data.get("analysis_insight"),
                summarization_insight=conflict_data.get("summarization_insight"),
            ))

        if roadmap_data:
            existing_roadmap = db.query(Roadmap).filter(Roadmap.session_id == session_id).first()
            if existing_roadmap:
                existing_roadmap.foundational_papers_json = (
                    roadmap_data.get("foundational_papers", [])
                )
                existing_roadmap.gap_areas_json = roadmap_data.get("gap_areas", [])
                existing_roadmap.next_queries_json = roadmap_data.get("next_query_suggestions", [])
            else:
                db.add(Roadmap(
                    session_id=session_id,
                    foundational_papers_json=roadmap_data.get("foundational_papers", []),
                    gap_areas_json=roadmap_data.get("gap_areas", []),
                    next_queries_json=roadmap_data.get("next_query_suggestions", []),
                ))

        db.commit()
    except Exception:
        db.rollback()
        raise

    return OrchestrateResponse(
        papers=papers_data,
        analysis=analysis_data,
        citations=citations_data,
        summaries=summaries_data,
        trace=trace_data,
        conflicts=conflicts_data,
    )


# ─── Conflicts ──────────────────────────────────────────────────────────────

@app.get(
    "/sessions/{session_id}/conflicts",
    response_model=list[ConflictResponse],
    tags=["Sessions", "Conflicts"],
)
def list_conflicts(
    session_id: str,
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user),
):
    _get_session_or_404(session_id, db, current_user_id)
    conflicts = (
        db.query(Conflict)
        .filter(Conflict.session_id == session_id)
        .order_by(Conflict.created_at.desc())
        .all()
    )
    return [ConflictResponse.model_validate(c) for c in conflicts]


@app.post(
    "/sessions/{session_id}/conflicts/{conflict_id}/resolve",
    tags=["Sessions", "Conflicts"],
)
def resolve_conflict(
    session_id: str,
    conflict_id: str,
    resolution: ConflictResolve,
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user),
):
    _get_session_or_404(session_id, db, current_user_id)
    conflict = (
        db.query(Conflict)
        .filter(Conflict.id == conflict_id, Conflict.session_id == session_id)
        .first()
    )
    if not conflict:
        raise HTTPException(status_code=404, detail="Conflict not found")
    conflict.resolved = True
    conflict.resolution_notes = resolution.resolution_notes
    db.commit()
    return {"status": "resolved", "conflict_id": conflict_id}


@app.post(
    "/sessions/{session_id}/detect-conflicts",
    response_model=ConflictDetectionResult,
    tags=["Sessions", "Conflicts"],
)
async def detect_conflicts(
    session_id: str,
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user),
):
    _get_session_or_404(session_id, db, current_user_id)
    papers = db.query(Paper).filter(Paper.session_id == session_id).all()
    analyses = db.query(Analysis).filter(Analysis.session_id == session_id).all()
    summaries = db.query(Summary).filter(
        Summary.paper_id.in_([p.id for p in papers])
    ).all() if papers else []

    papers_data = [{
        "id": p.id,
        "title": p.title,
        "authors": p.authors or [],
        "year": p.year,
        "abstract": p.abstract,
        "source": p.source,
    } for p in papers]

    analysis_data = {}
    for a in analyses:
        analysis_data[a.analysis_type] = a.data_json

    summaries_data = [{
        "paper_id": s.paper_id,
        "abstract_compression": s.abstract_compression,
        "key_contributions": s.key_contributions,
        "methodology": s.methodology,
        "limitations": s.limitations,
    } for s in summaries]

    result = await conflict_detector.detect_conflicts(papers_data, analysis_data, summaries_data)
    return ConflictDetectionResult(**result)


# ─── Papers ─────────────────────────────────────────────────────────────────

@app.patch("/papers/{paper_id}/note", response_model=NoteResponse, tags=["Papers"])
def update_note(
    paper_id: str,
    note_data: NoteCreate,
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user),
):
    paper = db.query(Paper).filter(Paper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    _get_session_or_404(paper.session_id, db, current_user_id)
    note = db.query(Note).filter(Note.paper_id == paper_id).first()
    if note:
        note.content = note_data.content
    else:
        note = Note(paper_id=paper_id, content=note_data.content)
        db.add(note)
    db.commit()
    db.refresh(note)
    return NoteResponse.model_validate(note)


# ─── Synthesis ───────────────────────────────────────────────────────────────

@app.post(
    "/sessions/{session_id}/synthesize",
    response_model=SynthesisResponse,
    tags=["Sessions", "Synthesis"],
)
async def synthesize(
    session_id: str,
    body: dict,
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user),
):
    _get_session_or_404(session_id, db, current_user_id)
    paper_ids = body.get("paper_ids", [])
    if not paper_ids:
        raise HTTPException(status_code=400, detail="No paper IDs provided")

    papers = db.query(Paper).filter(Paper.id.in_(paper_ids)).all()
    if not papers:
        raise HTTPException(status_code=404, detail="Papers not found")

    papers_data = [{
        "title": p.title,
        "abstract": p.abstract,
        "authors": p.authors or [],
        "year": p.year,
    } for p in papers]

    result = await summarizer.synthesize_papers(papers_data)

    synthesis = Synthesis(
        session_id=session_id,
        paper_ids=paper_ids,
        content=result.get("synthesis", ""),
    )
    db.add(synthesis)
    db.commit()
    db.refresh(synthesis)

    return SynthesisResponse(
        id=synthesis.id,
        session_id=synthesis.session_id,
        paper_ids=synthesis.paper_ids or [],
        content=synthesis.content,
        created_at=synthesis.created_at,
        updated_at=synthesis.updated_at,
    )


# ─── Exports ─────────────────────────────────────────────────────────────────

def _escape_bibtex(text: str | None) -> str:
    if text is None:
        return ""
    replacements = [
        ("\\", "\\\\"),
        ("{", "\\{"),
        ("}", "\\}"),
        ("$", "\\$"),
        ("&", "\\&"),
        ("#", "\\#"),
        ("_", "\\_"),
        ("%", "\\%"),
        ("~", "\\textasciitilde{}"),
        ("^", "\\textasciicircum{}"),
    ]
    for old, new in replacements:
        text = text.replace(old, new)
    return text

@app.get(
    "/sessions/{session_id}/export/bib",
    tags=["Sessions", "Export"],
)
def export_bib(
    session_id: str,
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user),
):
    _get_session_or_404(session_id, db, current_user_id)
    papers = db.query(Paper).filter(Paper.session_id == session_id).all()
    citations = (
        db.query(Citation)
        .filter(Citation.paper_id.in_([p.id for p in papers]))
        .all()
        if papers
        else []
    )
    citation_map = {c.paper_id: c for c in citations}

    bib_entries = []
    for i, paper in enumerate(papers):
        citation = citation_map.get(paper.id)
        author_last = (
            _escape_bibtex(
                paper.authors[0].split()[-1]
                if paper.authors
                else "Unknown"
            )
        )
        key = f"{author_last}{paper.year or 'nd'}"
        bib_entries.append(f"@article{{{_escape_bibtex(key)},")
        bib_entries.append(f"  title = {{{_escape_bibtex(paper.title)}}},")
        if paper.authors:
            bib_entries.append(f"  author = {{{_escape_bibtex(' and '.join(paper.authors))}}},")
        if paper.year:
            bib_entries.append(f"  year = {{{paper.year}}},")
        if citation and citation.apa:
            bib_entries.append(f"  note = {{{_escape_bibtex(citation.apa)}}},")
        bib_entries.append("}")

    bib_content = "\n".join(bib_entries)

    return Response(
        content=bib_content,
        media_type="application/x-bibtex",
        headers={"Content-Disposition": f"attachment; filename=orchestrix_{session_id[:8]}.bib"},
    )


@app.get(
    "/sessions/{session_id}/export/txt",
    tags=["Sessions", "Export"],
)
def export_txt(
    session_id: str,
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user),
):
    _get_session_or_404(session_id, db, current_user_id)
    papers = db.query(Paper).filter(Paper.session_id == session_id).all()
    citations = (
        db.query(Citation)
        .filter(Citation.paper_id.in_([p.id for p in papers]))
        .all()
        if papers
        else []
    )
    citation_map = {c.paper_id: c for c in citations}

    lines = []
    for paper in papers:
        citation = citation_map.get(paper.id)
        if citation and citation.apa:
            lines.append(citation.apa)
        else:
            author_str = ", ".join(paper.authors[:3]) if paper.authors else "Unknown"
            if len(paper.authors) > 3:
                author_str += ", et al."
            lines.append(f"{author_str} ({paper.year or 'n.d.'}). {paper.title}.")

    txt_content = "\n\n".join(lines)

    return Response(
        content=txt_content,
        media_type="text/plain",
        headers={"Content-Disposition": f"attachment; filename=orchestrix_{session_id[:8]}.txt"},
    )


# ─── Digests ─────────────────────────────────────────────────────────────────

@app.post(
    "/digests",
    response_model=ScheduledDigestResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Digests"],
)
def create_digest(
    digest_data: ScheduledDigestCreate,
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user),
):
    now = datetime.now(UTC)
    next_run = digest_scheduler.calculate_next_run(now, digest_data.frequency)
    digest = ScheduledDigest(
        user_id=current_user_id,
        name=digest_data.name,
        query=digest_data.query,
        frequency=digest_data.frequency,
        notify_email=digest_data.notify_email,
        next_run_at=next_run,
    )
    db.add(digest)
    db.commit()
    db.refresh(digest)

    scheduler.add_job(str(digest.id), digest.query, next_run)

    return ScheduledDigestResponse.model_validate(digest)


@app.get("/digests", response_model=list[ScheduledDigestResponse], tags=["Digests"])
def list_digests(db: Session = Depends(get_db), current_user_id: str = Depends(get_current_user)):
    digests = (
        db.query(ScheduledDigest)
        .filter(ScheduledDigest.user_id == current_user_id)
        .order_by(ScheduledDigest.created_at.desc())
        .all()
    )
    return [ScheduledDigestResponse.model_validate(d) for d in digests]


@app.get(
    "/digests/{digest_id}",
    response_model=ScheduledDigestWithRuns,
    tags=["Digests"],
)
def get_digest(
    digest_id: str,
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user),
):
    digest = _get_digest_or_404(digest_id, db, current_user_id)
    runs = (
        db.query(DigestRun)
        .filter(DigestRun.scheduled_digest_id == digest_id)
        .order_by(DigestRun.created_at.desc())
        .all()
    )
    response = ScheduledDigestResponse.model_validate(digest)
    return ScheduledDigestWithRuns(
        **response.model_dump(),
        runs=[DigestRunResponse.model_validate(r) for r in runs],
    )


@app.delete("/digests/{digest_id}", tags=["Digests"])
def delete_digest(
    digest_id: str,
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user),
):
    digest = _get_digest_or_404(digest_id, db, current_user_id)
    scheduler.remove_job(digest_id)
    db.delete(digest)
    db.commit()
    return {"message": "Digest deleted"}


@app.patch(
    "/digests/{digest_id}/toggle",
    response_model=ScheduledDigestResponse,
    tags=["Digests"],
)
def toggle_digest(
    digest_id: str,
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user),
):
    digest = _get_digest_or_404(digest_id, db, current_user_id)
    digest.is_active = not digest.is_active
    if digest.is_active:
        now = datetime.now(UTC)
        next_run = digest_scheduler.calculate_next_run(now, digest.frequency)
        digest.next_run_at = next_run
        scheduler.add_job(digest_id, digest.query, next_run)
    else:
        scheduler.remove_job(digest_id)
    db.commit()
    db.refresh(digest)
    return ScheduledDigestResponse.model_validate(digest)


@app.post(
    "/digests/{digest_id}/run",
    response_model=DigestRunResponse,
    tags=["Digests"],
)
def run_digest_manual(
    digest_id: str,
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user),
):
    digest = _get_digest_or_404(digest_id, db, current_user_id)
    scheduler.trigger_manual_run(digest_id)
    run = DigestRun(
        scheduled_digest_id=digest_id,
        query=digest.query,
        status="running",
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return DigestRunResponse.model_validate(run)


@app.get("/digests/{digest_id}/preview", tags=["Digests"])
async def preview_digest(
    digest_id: str,
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user),
):
    digest = _get_digest_or_404(digest_id, db, current_user_id)
    sessions = (
        db.query(SessionModel)
        .filter(SessionModel.query == digest.query)
        .order_by(SessionModel.created_at.desc())
        .first()
    )
    existing_ids = []
    if sessions:
        existing_papers = db.query(Paper).filter(Paper.session_id == sessions.id).all()
        existing_ids = [p.external_id for p in existing_papers if p.external_id]

    result = await digest_scheduler.run_digest(
        query=digest.query,
        last_run_at=digest.last_run_at,
        existing_external_ids=existing_ids,
        limit=20,
    )

    return {
        "query": digest.query,
        "threshold_date": result.get("threshold_date"),
        "new_papers_preview": result.get("new_papers", [])[:5],
        "total_new_count": result.get("total_new", 0),
        "is_first_run": result.get("is_first_run", True),
    }


# ─── Roadmap ────────────────────────────────────────────────────────────────

@app.post(
    "/sessions/{session_id}/roadmap",
    response_model=RoadmapResponse,
    tags=["Sessions", "Roadmap"],
)
async def generate_roadmap(
    session_id: str,
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user),
):
    db_session = _get_session_or_404(session_id, db, current_user_id)
    result = await orchestrate(db_session.query, session_id)
    roadmap_data = result.get("roadmap")
    if not roadmap_data:
        raise HTTPException(status_code=500, detail="Roadmap generation failed")

    existing = db.query(Roadmap).filter(Roadmap.session_id == session_id).first()
    if existing:
        existing.foundational_papers_json = roadmap_data.get("foundational_papers", [])
        existing.gap_areas_json = roadmap_data.get("gap_areas", [])
        existing.next_queries_json = roadmap_data.get("next_query_suggestions", [])
    else:
        db.add(Roadmap(
            session_id=session_id,
            foundational_papers_json=roadmap_data.get("foundational_papers", []),
            gap_areas_json=roadmap_data.get("gap_areas", []),
            next_queries_json=roadmap_data.get("next_query_suggestions", []),
        ))
    db.commit()
    return RoadmapResponse(**roadmap_data)


@app.get(
    "/sessions/{session_id}/roadmap",
    response_model=RoadmapResponse,
    tags=["Sessions", "Roadmap"],
)
def get_roadmap(
    session_id: str,
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user),
):
    _get_session_or_404(session_id, db, current_user_id)
    roadmap_record = db.query(Roadmap).filter(Roadmap.session_id == session_id).first()
    if not roadmap_record:
        raise HTTPException(status_code=404, detail="Roadmap not found. Generate one first.")
    return RoadmapResponse(
        foundational_papers=roadmap_record.foundational_papers_json or [],
        gap_areas=roadmap_record.gap_areas_json or [],
        next_query_suggestions=roadmap_record.next_queries_json or [],
    )


@app.post(
    "/sessions/{session_id}/roadmap/query",
    tags=["Sessions", "Roadmap"],
)
async def execute_roadmap_query(
    session_id: str,
    query: str,
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user),
):
    _get_session_or_404(session_id, db, current_user_id)
    result = await orchestrate(query, session_id, page=0)
    return {"triggered_query": query, "orchestration_result": result}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
