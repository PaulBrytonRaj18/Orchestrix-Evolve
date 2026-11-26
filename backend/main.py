"""Orchestrix API — application wiring only (routers hold the endpoints)."""

from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from config import get_settings
from database import close_engine, engine, init_db, is_postgres
from routers import auth as auth_router
from routers import digests, jobs, sessions
from scheduler import scheduler
from schemas import HealthResponse
from services.jobs import job_manager

APP_VERSION = "2.2.0"
settings = get_settings()

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("orchestrix")
START_TIME = time.monotonic()


@asynccontextmanager
async def lifespan(_: FastAPI):
    for problem in settings.configuration_errors():
        logger.warning("Configuration: %s", problem)
    await run_in_threadpool(init_db)
    logger.info("Database: %s", "PostgreSQL" if is_postgres() else "SQLite")
    await job_manager.start()
    if settings.enable_scheduler:
        scheduler.start()
    yield
    await job_manager.shutdown()
    scheduler.stop()
    close_engine()


app = FastAPI(
    title="Orchestrix API",
    version=APP_VERSION,
    lifespan=lifespan,
    docs_url=None if settings.env == "production" else "/docs",
    redoc_url=None,
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    """Request id + timing + security headers in one middleware."""
    request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
    request.state.request_id = request_id
    started = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    response.headers.update(
        {
            "X-Request-ID": request_id,
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
        }
    )
    logger.info(
        "%s %s %s %dms req=%s",
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
        request_id,
    )
    return response


app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    expose_headers=["Content-Disposition", "X-Request-ID"],
    max_age=600,
)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    headers = dict(exc.headers or {})
    headers["X-Request-ID"] = getattr(request.state, "request_id", "")
    return JSONResponse(
        status_code=exc.status_code, content={"detail": exc.detail}, headers=headers
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", "unknown")
    logger.error("Unhandled exception req=%s", request_id, exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "request_id": request_id},
        headers={"X-Request-ID": request_id},
    )


@app.get("/health", response_model=HealthResponse, tags=["Health"])
def health_check() -> HealthResponse:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:
        logger.exception("Health check: database unreachable")
        db_status = "error"
    return HealthResponse(
        status="ok" if db_status == "ok" else "degraded",
        version=APP_VERSION,
        database=db_status,
        uptime_seconds=round(time.monotonic() - START_TIME, 1),
        llm_enabled=settings.llm_enabled,
    )


app.include_router(auth_router.router)
app.include_router(sessions.router)
app.include_router(sessions.notes_router)
app.include_router(digests.router)
app.include_router(jobs.router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000)
