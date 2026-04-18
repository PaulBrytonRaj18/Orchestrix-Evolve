from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from typing import List, Optional
import os
import logging
from datetime import datetime, timezone
from dotenv import load_dotenv

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

load_dotenv()

# Import database functions
from database import get_db, init_db, close_engine, is_postgres
from models import (
    User,
    Session as SessionModel,
    Paper,
    Analysis,
    Summary,
    Synthesis,
    Citation,
    Note,
    Conflict,
    ScheduledDigest,
    DigestRun,
    Roadmap,
)
from schemas import (
    UserCreate,
    UserLogin,
    UserResponse,
    UserUpdate,
    TokenResponse,
    SessionCreate,
    SessionResponse,
    SessionFullResponse,
    PaperResponse,
    PaperWithDetails,
    AnalysisResponse,
    SummaryResponse,
    SynthesisResponse,
    CitationResponse,
    NoteCreate,
    NoteResponse,
    OrchestrateResponse,
    HealthResponse,
    ConflictResponse,
    ConflictResolve,
    ScheduledDigestCreate,
    ScheduledDigestResponse,
    DigestRunResponse,
    ScheduledDigestWithRuns,
    ConflictDetectionResult,
    RoadmapResponse,
)
from auth import (
    get_current_user,
    get_current_user_optional,
    get_supabase_client,
)
from orchestrator import orchestrate
from agents import summarizer, conflict_detector, digest_scheduler, roadmap
from scheduler import scheduler


# CORS Configuration
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
CORS_ORIGINS = [
    FRONTEND_URL,
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:3000",
]

# Create app BEFORE adding middleware
app = FastAPI(title="Orchestrix API", version="2.0.0")

# Add CORS middleware immediately after app creation
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods="*",
    allow_headers="*",
    expose_headers=["Content-Disposition"],
    max_age=600,
)


# Lifespan for startup/shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
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


# Update app with lifespan
app.router.lifespan_context = lifespan


@app.get("/health", response_model=HealthResponse, tags=["Health"])
def health_check():
    return {"status": "ok"}


@app.post(
    "/auth/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Auth"],
)
def register(user_data: UserCreate):
    """
    Register a new user with Supabase Auth.
    Note: Supabase handles password hashing automatically.
    """
    try:
        supabase = get_supabase_client()

        # Sign up with Supabase
        response = supabase.auth.sign_up(
            {
                "email": user_data.email,
                "password": user_data.password,
                "options": {"data": {"username": user_data.username}},
            }
        )

        if response.user is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=response.data.get("message", "Registration failed"),
            )

        # Return the response (Supabase handles token generation)
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

    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Registration failed: {str(e)}",
        )


@app.post("/auth/login", response_model=TokenResponse, tags=["Auth"])
def login(user_data: UserLogin):
    """
    Login with Supabase Auth.
    Returns JWT tokens for API access.
    """
    try:
        supabase = get_supabase_client()

        response = supabase.auth.sign_in_with_password(
            {"email": user_data.email, "password": user_data.password}
        )

        if response.user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
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
    """
    Logout current user (invalidate tokens).
    """
    try:
        supabase = get_supabase_client()
        supabase.auth.sign_out()
        return {"message": "Successfully logged out"}
    except Exception as e:
        logger.error(f"Logout error: {str(e)}")
        return {"message": "Logged out (token may be invalid)"}


@app.get("/auth/me", response_model=UserResponse, tags=["Auth"])
def get_current_user_info(current_user_id: str = Depends(get_current_user)):
    """
    Get current authenticated user's profile from Supabase.
    """
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
def refresh_token(refresh_data: dict):
    """
    Refresh access token using refresh token.
    """
    try:
        supabase = get_supabase_client()

        refresh_token = refresh_data.get("refresh_token")
        if not refresh_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Refresh token required"
            )

        response = supabase.auth.refresh_session(refresh_token)

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
                "created_at": response.user.created_at
                if response.user
                else datetime.now(timezone.utc),
            },
        }
    except Exception as e:
        logger.error(f"Token refresh error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Failed to refresh token"
        )


@app.patch("/auth/me", response_model=UserResponse, tags=["Auth"])
def update_current_user(
    user_update: UserUpdate,
    current_user_id: str = Depends(get_current_user),
):
    """
    Update current user's profile via Supabase.
    Note: Password updates require Supabase Admin API or user to use reset password flow.
    """
    try:
        supabase = get_supabase_client()

        # Get current user from Supabase
        response = supabase.auth.get_user()

        if not response.user:
            raise HTTPException(status_code=404, detail="User not found")

        # Note: Username is stored in user_metadata - updating it requires admin API
        # For now, just return current user info
        # Full profile updates would require Supabase Admin or Edge Functions

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


@app.post("/sessions", response_model=SessionResponse, tags=["Sessions"])
@app.get("/sessions", response_model=List[SessionResponse], tags=["Sessions"])
@app.get(
    "/sessions/{session_id}", response_model=SessionFullResponse, tags=["Sessions"]
)
@app.post(
    "/sessions/{session_id}/orchestrate",
    response_model=OrchestrateResponse,
    tags=["Sessions", "Orchestration"],
)
@app.get(
    "/sessions/{session_id}/conflicts",
    response_model=List[ConflictResponse],
    tags=["Sessions", "Conflicts"],
)
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
    db_session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not db_session:
        raise HTTPException(status_code=404, detail="Session not found")

    if db_session.user_id and db_session.user_id != current_user_id:
        raise HTTPException(status_code=403, detail="Access denied")

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
@app.patch("/papers/{paper_id}/note", response_model=NoteResponse, tags=["Papers"])
@app.post("/sessions/{session_id}/synthesize", tags=["Sessions", "Synthesis"])
@app.get("/sessions/{session_id}/export/bib", tags=["Sessions", "Export"])
@app.get("/sessions/{session_id}/export/txt", tags=["Sessions", "Export"])
def export_txt(
    session_id: str,
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user),
):
    db_session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not db_session:
        raise HTTPException(status_code=404, detail="Session not found")

    if db_session.user_id and db_session.user_id != current_user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    papers = db.query(Paper).filter(Paper.session_id == session_id).all()
    citations = (
        db.query(Citation).filter(Citation.paper_id.in_([p.id for p in papers])).all()
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
        headers={
            "Content-Disposition": f"attachment; filename=orchestrix_{session_id[:8]}.txt"
        },
    )


@app.post("/digests", response_model=ScheduledDigestResponse, tags=["Digests"])
@app.get("/digests", response_model=List[ScheduledDigestResponse], tags=["Digests"])
@app.get(
    "/digests/{digest_id}", response_model=ScheduledDigestWithRuns, tags=["Digests"]
)
@app.delete("/digests/{digest_id}", tags=["Digests"])
@app.patch("/digests/{digest_id}/toggle", tags=["Digests"])
@app.post("/digests/{digest_id}/run", tags=["Digests"])
@app.get("/digests/{digest_id}/preview", tags=["Digests"])
async def preview_digest(
    digest_id: str,
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user),
):
    digest = db.query(ScheduledDigest).filter(ScheduledDigest.id == digest_id).first()
    if not digest:
        raise HTTPException(status_code=404, detail="Digest not found")

    if digest.user_id and digest.user_id != current_user_id:
        raise HTTPException(status_code=403, detail="Access denied")

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


@app.post(
    "/sessions/{session_id}/roadmap",
    response_model=RoadmapResponse,
    tags=["Sessions", "Roadmap"],
)
@app.get(
    "/sessions/{session_id}/roadmap",
    response_model=RoadmapResponse,
    tags=["Sessions", "Roadmap"],
)
@app.post("/sessions/{session_id}/roadmap/query", tags=["Sessions", "Roadmap"])
async def execute_roadmap_query(
    session_id: str,
    query: str,
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user),
):
    db_session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not db_session:
        raise HTTPException(status_code=404, detail="Session not found")

    if db_session.user_id and db_session.user_id != current_user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    result = await orchestrate(query, session_id, page=0)

    return {"triggered_query": query, "orchestration_result": result}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
