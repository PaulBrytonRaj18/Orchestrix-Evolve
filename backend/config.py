"""Centralised, typed application settings.

Every environment variable the backend reads is declared here once, validated by
pydantic-settings, and exposed through :func:`get_settings`. Modules must not call
``os.getenv`` / ``load_dotenv`` themselves.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_PLACEHOLDER_VALUES = {
    "",
    "change-me",
    "default",
    "your-groq-api-key",
    "your-supabase-service-role-key",
    "your-secret-key-here-change-in-production",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    # ── Runtime ────────────────────────────────────────────────────────────
    env: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"

    # ── Database ───────────────────────────────────────────────────────────
    database_url: str = ""
    supabase_db_url: str = ""
    sqlite_db_path: str = "./orchestrix.db"
    db_pool_size: int = 5
    db_max_overflow: int = 10

    # ── Supabase auth ──────────────────────────────────────────────────────
    supabase_url: str = ""
    supabase_service_key: str = ""
    # Legacy HS256 projects sign user JWTs with this secret. New projects use
    # asymmetric keys published at <SUPABASE_URL>/auth/v1/.well-known/jwks.json.
    supabase_jwt_secret: str = ""
    supabase_jwt_audience: str = "authenticated"

    # ── HTTP / CORS ────────────────────────────────────────────────────────
    frontend_url: str = "http://localhost:5173"
    cors_origins: str = ""

    # ── LLM (Groq) ─────────────────────────────────────────────────────────
    groq_api_key: str = ""
    groq_model: str = "llama-3.1-8b-instant"
    groq_timeout: float = 30.0
    groq_max_concurrency: int = Field(default=3, ge=1)
    groq_rate_limit_rpm: int = Field(default=30, ge=1)

    # ── Orchestration ──────────────────────────────────────────────────────
    # "static" runs the full, dependency-ordered agent graph (fast, deterministic).
    # "llm" lets the Manager agent pick a subset; its plan is validated and
    # dependency-completed before execution.
    orchestrator_planner: Literal["static", "llm"] = "static"
    summarize_top_n: int = Field(default=10, ge=0)
    summary_batch_size: int = Field(default=4, ge=1, le=8)  # papers per LLM request
    # Optional: re-score the top K results with one LLM call (needs GROQ_API_KEY).
    # 0 disables. The LLM score is blended 50/50 with the measured hybrid score.
    llm_rerank_top_k: int = Field(default=0, ge=0, le=30)

    # ── Discovery sources ──────────────────────────────────────────────────
    semantic_scholar_url: str = "https://api.semanticscholar.org/graph/v1/paper/search"
    semantic_scholar_api_key: str = ""
    arxiv_url: str = "https://export.arxiv.org/api/query"
    openalex_url: str = "https://api.openalex.org/works"
    openalex_mailto: str = ""  # joins OpenAlex's faster "polite pool"
    discovery_timeout: float = 20.0
    discovery_per_source_limit: int = Field(default=50, ge=1, le=100)
    discovery_return_top: int = Field(default=20, ge=1)
    # Wall-clock budget for one discovery round. Sources still running are cancelled
    # and the search continues with whatever arrived.
    discovery_deadline: float = Field(default=8.0, gt=0)
    # After a source fails (rate limit, outage, deadline) it is skipped for this long
    # instead of costing every search its retries again. 0 disables the cooldown.
    source_failure_cooldown_seconds: float = Field(default=60.0, ge=0)

    # ── Embeddings (local, free: fastembed/ONNX) ────────────────────────────
    embeddings_enabled: bool = True
    embedding_model: str = "BAAI/bge-small-en-v1.5"  # see services/embeddings.MODELS
    embedding_cache_dir: str = ""  # model files; empty → fastembed's default cache
    embedding_threads: int = Field(default=0, ge=0)  # 0 → ONNX Runtime decides
    embedding_max_chars: int = Field(default=600, ge=100, le=4000)

    # ── Source response cache ──────────────────────────────────────────────
    source_cache_enabled: bool = True
    source_cache_ttl_seconds: int = Field(default=86_400, ge=0)  # regular searches
    source_cache_since_ttl_seconds: int = Field(default=3_600, ge=0)  # "new since" digests
    source_cache_memory_items: int = Field(default=256, ge=0)

    # ── Background jobs ────────────────────────────────────────────────────
    job_max_concurrency: int = Field(default=4, ge=1)  # running jobs per process
    job_max_active_per_user: int = Field(default=3, ge=1)
    job_heartbeat_seconds: float = Field(default=15.0, gt=0)
    job_stale_after_seconds: float = Field(default=90.0, gt=0)  # no heartbeat → orphaned
    sse_keepalive_seconds: float = Field(default=15.0, gt=0)

    # ── Scheduler ──────────────────────────────────────────────────────────
    # Run the digest scheduler in exactly one process (e.g. one replica or a
    # dedicated worker). With several uvicorn workers set this to false on all
    # but one, otherwise every worker fires every digest.
    enable_scheduler: bool = True

    @field_validator("log_level")
    @classmethod
    def _upper(cls, v: str) -> str:
        return v.upper()

    # ── Derived values ─────────────────────────────────────────────────────
    @property
    def resolved_database_url(self) -> str:
        url = self.supabase_db_url or self.database_url
        if not url:
            return f"sqlite:///{self.sqlite_db_path}"
        # psycopg 3 is the maintained Postgres driver; normalise bare schemes to it.
        for prefix in ("postgres://", "postgresql://", "postgresql+psycopg2://"):
            if url.startswith(prefix):
                return "postgresql+psycopg://" + url[len(prefix) :]
        return url

    @property
    def is_postgres(self) -> bool:
        return self.resolved_database_url.startswith("postgresql")

    @property
    def allowed_origins(self) -> list[str]:
        if self.cors_origins:
            return [o.strip() for o in self.cors_origins.split(",") if o.strip()]
        return [
            self.frontend_url,
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:3000",
        ]

    @property
    def llm_enabled(self) -> bool:
        return self.groq_api_key not in _PLACEHOLDER_VALUES

    def configuration_errors(self) -> list[str]:
        """Problems worth surfacing at startup (never raised: dev must still boot)."""
        errors: list[str] = []
        if not self.supabase_url:
            errors.append("SUPABASE_URL is not set — authenticated endpoints will fail")
        if self.supabase_service_key in _PLACEHOLDER_VALUES:
            errors.append("SUPABASE_SERVICE_KEY is not set — /auth/* endpoints will fail")
        if not self.llm_enabled:
            errors.append("GROQ_API_KEY is not set — LLM summaries are disabled")
        return errors


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
